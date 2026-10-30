"""Fast-cut demo edit from a native-resolution, multi-part take.

    python edit.py <demo dir> <out.mp4>

Reads timeline.json (command times, active-window geometry, recording parts)
and sync.json ({"part_lag": [seconds per part]}: how long after its logged
start each part's first frame was captured).

Each step becomes: command spoken (screen still) -> invisible cut over the
dead time while handsfree waits for silence -> the result appearing. Views
zoom onto the window Hyprland reported (never past 1.8x, so the 3454-wide
source stays sharp at 1080p). A kinetic hook, an install card and an end
card wrap it, and the ElevenLabs voiceover is mixed on top.
"""

import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

D, OUT = Path(sys.argv[1]), Path(sys.argv[2])
W, H, FPS = 1920, 1080, 30
script = json.loads((D / "script.json").read_text())
dur = json.loads((D / "durations.json").read_text())
tl = json.loads((D / "timeline.json").read_text())
sync = json.loads((D / "sync.json").read_text())
steps = {s["step"]: s for s in tl["steps"]}
ACCENT = (239, 68, 68)
PLAY_LAG = 0.08
MAX_ZOOM = 1.8

# ------------------------------------------------------------------ source parts
parts = []
for k, p in enumerate(tl["parts"]):
    path = D / Path(p["path"]).name
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    first = p["start"] + sync["part_lag"][k]
    parts.append({"path": path, "first": first, "last": first + n / 30.0, "cap": cap, "index": -1, "frame": None})
SW = int(parts[0]["cap"].get(cv2.CAP_PROP_FRAME_WIDTH))
SH = int(parts[0]["cap"].get(cv2.CAP_PROP_FRAME_HEIGHT))
mon = tl["monitor"]
PX = SW / (mon["width"] / mon["scale"])  # source px per logical px


def raw_at(t):
    """Frame at wall-clock take time t (seconds), from whichever part covers it."""
    part = parts[0]
    for p in parts:
        if t >= p["first"]:
            part = p
    t = min(max(t, part["first"]), part["last"] - 1 / 30)
    want = int((t - part["first"]) * 30)
    if want < part["index"]:
        part["cap"].set(cv2.CAP_PROP_POS_FRAMES, want)
        part["index"] = want - 1
    while part["index"] < want:
        ok, f = part["cap"].read()
        if not ok:
            break
        part["index"] += 1
        part["frame"] = f
    return part["frame"]


def change_series():
    """Mean frame difference at 240x135 for every frame of the take, by wall time."""
    series = []
    for p in parts:
        cap = cv2.VideoCapture(str(p["path"]))
        prev, n = None, 0
        while True:
            ok, f = cap.read()
            if not ok:
                break
            g = cv2.resize(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (240, 135)).astype(np.float32)
            if prev is not None:
                series.append((p["first"] + n / 30.0, float(np.abs(g - prev).mean())))
            prev, n = g, n + 1
    return series


CHANGES = change_series()


def action_time(after, limit=3.0, threshold=0.6):
    for t, v in CHANGES:
        if after <= t <= after + limit and v > threshold:
            return t
    return None


# ------------------------------------------------------------------ views
FULL_STEPS = {"Next theme", "Workspace two", "Workspace one", "Show grid", "Close grid", "Stop listening", "Close window"}
FULL = (SW / 2, SH / 2, SW)


def fit(x, y, w, h, pad=0.07):
    w2, h2 = w * (1 + 2 * pad), h * (1 + 2 * pad)
    vw = min(max(w2, h2 * 16 / 9, SW / MAX_ZOOM), SW)
    return (x + w / 2, y + h / 2, vw)


def view_for(i):
    caption = script["steps"][i - 1]["caption"]
    if caption in FULL_STEPS:
        return FULL
    if caption == "Five":
        return (SW / 2, SH / 2, SW / MAX_ZOOM)
    win = steps[i].get("window") or {}
    if not win.get("at"):
        return FULL
    (x, y), (w, h) = win["at"], win["size"]
    return fit(x * PX, y * PX, w * PX, h * PX)


# ------------------------------------------------------------------ build the cut list
# segment: dict(kind, a, b (wall times) or length, step, view, from, xfade)
segs = [{"kind": "hook", "len": dur["hook"] + 0.85}]  # hold the full sentence a beat
la = tl["listen_at"]
segs.append({"kind": "footage", "a": la - 0.1, "b": la - 0.1 + max(1.7, dur["intro"] + 0.3), "view": "bar", "xfade": True})
SKIP = {9, 21}  # a second "close window" and "stop listening" show nothing new
USED = [i for i in range(1, len(script["steps"]) + 1) if i not in SKIP]
prev_view = FULL
for i in USED:
    spec, s = script["steps"][i - 1], steps[i]
    view = view_for(i)
    start = s["narration_at"] if s["narration_at"] is not None else s["command_at"] - 0.05
    act = action_time(s["command_end"] + 0.15)
    if act is not None:
        # Cut to the result while the command's last syllable is still playing:
        # the wait for end-of-speech + transcription (~1 s) is cut out.
        spoken = s["command_at"] + PLAY_LAG + max(0.45, 0.62 * dur[f"c{i:02d}"])
        segs.append({"kind": "footage", "a": start, "b": spoken, "step": i, "view": view,
                     "from": prev_view, "xfade": True, "first": True})
        segs.append({"kind": "footage", "a": act - 0.04, "b": act + max(0.6, spec["show"] * 0.55), "step": i,
                     "view": view, "from": view, "xfade": False})
    else:
        segs.append({"kind": "footage", "a": start, "b": s["command_end"] + spec["show"], "step": i, "view": view,
                     "from": prev_view, "xfade": True, "first": True})
    prev_view = view
segs.append({"kind": "install", "len": dur["install"] + 0.7})
segs.append({"kind": "end", "len": dur["outro"] + 1.1})

t = 0.0
for sg in segs:
    sg["start"] = t
    sg["len"] = sg.get("len", (sg.get("b", 0) - sg.get("a", 0)))
    t += sg["len"]
TOTAL = t


def out_of(i, wall):
    """Output time for a wall time inside step i's segments."""
    for sg in segs:
        if sg.get("step") == i and sg["a"] <= wall <= sg["b"]:
            return sg["start"] + wall - sg["a"]
    first = next(sg for sg in segs if sg.get("step") == i)
    return first["start"]


def step_end(i):
    return max(sg["start"] + sg["len"] for sg in segs if sg.get("step") == i)


def step_start(i):
    return min(sg["start"] for sg in segs if sg.get("step") == i)


# ------------------------------------------------------------------ drawing
def font(size, weight="Bold"):
    f = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def mono(size):
    return ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", size)


def bbox(d, text, f):
    l, t_, r, b = d.textbbox((0, 0), text, font=f)
    return r - l, b - t_, l, t_


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp_view(a, b, k):
    w = math.exp(math.log(a[2]) * (1 - k) + math.log(b[2]) * k)
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, w)


def render_view(frame, view):
    cx, cy, w = view
    h = w * 9 / 16
    x0 = min(max(cx - w / 2, 0), SW - w)
    y0 = min(max(cy - h / 2, 0), SH - h)
    ix, iy = int(x0), int(y0)
    iw, ih = min(int(math.ceil(w)) + 2, SW - ix), min(int(math.ceil(h)) + 2, SH - iy)
    crop = frame[iy:iy + ih, ix:ix + iw]
    s = W / w
    scaled = cv2.resize(crop, (max(W, int(round(iw * s))), max(H, int(round(ih * s)))),
                        interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    m = np.float32([[1, 0, -(x0 - ix) * s], [0, 1, -(y0 - iy) * s]])
    return cv2.warpAffine(scaled, m, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE), (x0, y0, s)


def to_bgr(img):
    return cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def overlay(frame, layer, alpha=1.0, scale=1.0):
    if alpha <= 0:
        return frame
    if scale != 1.0:
        w, h = layer.size
        small = layer.resize((int(w * scale), int(h * scale)), Image.BILINEAR)
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.alpha_composite(small, ((W - small.size[0]) // 2, (H - small.size[1]) // 2 + int((1 - scale) * 380)))
        layer = canvas
    arr = np.asarray(layer, dtype=np.float32)
    a = arr[..., 3:4] / 255.0 * alpha
    return (frame * (1 - a) + arr[..., :3][..., ::-1] * a).astype(np.uint8)


def pill(text):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f, small = font(58, "Bold"), font(26, "Bold")
    quoted = f"“{text}”"
    tw, th, tl_, tt = bbox(d, quoted, f)
    lw, lh, ll, lt = bbox(d, "YOU SAY", small)
    width, height = 44 * 2 + 22 + 24 + max(tw, lw), 152
    x0, y0 = (W - width) // 2, H - height - 60
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + 12, x0 + width, y0 + height + 12), 40, fill=(0, 0, 0, 150))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)))
    d.rounded_rectangle((x0, y0, x0 + width, y0 + height), 40, fill=(16, 18, 22, 240), outline=(255, 255, 255, 45), width=2)
    cx = x0 + 55
    d.ellipse((cx - 11, y0 + 76 - 11, cx + 11, y0 + 76 + 11), fill=ACCENT + (255,))
    tx = x0 + 90
    d.text((tx - ll, y0 + 26 - lt), "YOU SAY", font=small, fill=ACCENT + (255,))
    d.text((tx - tl_, y0 + 62 - tt), quoted, font=f, fill=(255, 255, 255, 255))
    return img


def headline(text):
    """Narration as a bold top headline, so it never collides with the pill."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(50, "Bold")
    tw, th, l, t_ = bbox(d, text, f)
    x0, y = (W - tw) // 2, 70
    d.rounded_rectangle((x0 - 34, y - 24, x0 + tw + 34, y + th + 28), 22, fill=(0, 0, 0, 175))
    d.text((x0 - l, y - t_), text, font=f, fill=(255, 255, 255, 252))
    return img


def card_bg(frame):
    img = Image.fromarray(cv2.cvtColor(cv2.resize(frame, (W, H), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB))
    return Image.blend(img.filter(ImageFilter.GaussianBlur(30)), Image.new("RGB", (W, H), (9, 10, 14)), 0.66)


def text_center(d, text, f, y, fill):
    w, h, l, t_ = bbox(d, text, f)
    d.text(((W - w) // 2 - l, y - t_), text, font=f, fill=fill)
    return h


first_bg = card_bg(raw_at(parts[0]["first"] + 0.3))

HOOK_WORDS = ["What", "if", "you", "could", "just", "talk", "to", "your", "desktop?"]


def hook_frame(t):
    img = first_bg.copy().convert("RGBA")
    d = ImageDraw.Draw(img)
    f = font(104, "Bold")
    shown = min(len(HOOK_WORDS), int(t / (dur["hook"] * 0.8) * len(HOOK_WORDS)) + 1)
    rows = (HOOK_WORDS[:5], HOOK_WORDS[5:])
    for r, words in enumerate(rows):
        text = " ".join(words)
        tw, th, l, tt = bbox(d, text, f)
        x, y = (W - tw) // 2 - l, 360 + r * 150
        for k, word in enumerate(words):
            idx = (0 if r == 0 else len(rows[0])) + k
            if idx >= shown:
                continue
            px = d.textlength(" ".join(words[:k]) + (" " if k else ""), font=f)
            pop = ease((t - idx * dur["hook"] * 0.8 / len(HOOK_WORDS)) / 0.12)
            color = ACCENT if word in ("talk", "desktop?") else (255, 255, 255)
            d.text((x + px, y - tt + (1 - pop) * 18), word, font=f, fill=color + (int(255 * pop),))
    return to_bgr(img)


INSTALL_LINES = ["git clone https://github.com/Saba-Burduli/omarchy-handsfree",
                 "cd omarchy-handsfree && ./install.sh"]
INSTALL_LEN = dur["install"] + 0.7


def install_frame(t):
    img = first_bg.copy().convert("RGBA")
    d = ImageDraw.Draw(img)
    k0 = ease(t / 0.3)
    text_center(d, "Install in one command", font(76, "Bold"), 230 + (1 - k0) * 20, (255, 255, 255, int(255 * k0)))
    f = mono(40)
    box = (190, 360, W - 190, 590)
    d.rounded_rectangle(box, 26, fill=(14, 16, 20, 245), outline=ACCENT + (190,), width=3)
    for k, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse((box[0] + 30 + k * 34, box[1] + 26, box[0] + 50 + k * 34, box[1] + 46), fill=c + (255,))
    total = sum(len(s) for s in INSTALL_LINES)
    typed = int(min(1.0, t / (INSTALL_LEN * 0.45)) * total)
    y = box[1] + 84
    for line in INSTALL_LINES:
        part, typed = line[:max(0, typed)], typed - len(line)
        d.text((box[0] + 50, y), "$", font=f, fill=ACCENT + (255,))
        d.text((box[0] + 50 + d.textlength("$ ", font=f), y), part, font=f, fill=(235, 238, 242, 255))
        y += 64
    if t > INSTALL_LEN * 0.5:
        k = ease((t - INSTALL_LEN * 0.5) / 0.3)
        fk, ft = font(46, "Bold"), font(46, "Semibold")
        keys = ["Super", "Alt", "V"]
        widths = [d.textlength(x, font=fk) + 64 for x in keys]
        total_w = sum(widths) + 2 * 74 + d.textlength("and talk", font=ft) + 44
        x, y0 = (W - total_w) / 2, 680 + (1 - k) * 30
        for key, kw in zip(keys, widths):
            d.rounded_rectangle((x, y0, x + kw, y0 + 90), 16, fill=(30, 33, 40, int(255 * k)), outline=(255, 255, 255, int(110 * k)), width=2)
            d.text((x + 32, y0 + 18), key, font=fk, fill=(255, 255, 255, int(255 * k)))
            x += kw
            if key != "V":
                d.text((x + 24, y0 + 18), "+", font=fk, fill=(170, 175, 185, int(255 * k)))
                x += 74
        d.text((x + 44, y0 + 18), "and talk", font=ft, fill=ACCENT + (int(255 * k),))
    return to_bgr(img)


def end_frame(t, bg):
    img = bg.copy().convert("RGBA")
    d = ImageDraw.Draw(img)
    k = ease(t / 0.45)
    a = int(255 * k)
    y = 290 + (1 - k) * 30
    y += text_center(d, "Omarchy Hands-free", font(116, "Bold"), y, (255, 255, 255, a)) + 46
    y += text_center(d, "Voice control for Omarchy. Offline. Free and open source.", font(42, "Medium"), y, (220, 224, 230, a)) + 72
    f = mono(46)
    url = "github.com/Saba-Burduli/omarchy-handsfree"
    w, h, l, tt = bbox(d, url, f)
    d.rounded_rectangle(((W - w) // 2 - 44, y - 30, (W + w) // 2 + 44, y + h + 34), 22, fill=(14, 16, 20, int(240 * k)),
                        outline=ACCENT + (int(220 * k),), width=3)
    d.text(((W - w) // 2 - l, y - tt), url, font=f, fill=(255, 255, 255, a))
    text_center(d, "Edited for pace: each action takes about a second.   Voice: ElevenLabs", font(26, "Medium"), H - 70,
                (150, 155, 165, int(200 * k)))
    return to_bgr(img)


# ------------------------------------------------------------------ captions
captions = []
intro_seg = segs[1]
captions.append((intro_seg["start"] + 0.05, intro_seg["start"] + intro_seg["len"] - 0.05, headline("Meet Omarchy Hands-free."), "head"))
for i in USED:
    spec, s = script["steps"][i - 1], steps[i]
    st = step_start(i)
    if spec.get("narration"):
        captions.append((st + 0.03, st + dur[f"n{i:02d}"] + 0.2, headline(spec["narration"]), "head"))
    captions.append((out_of(i, s["command_at"] + PLAY_LAG), step_end(i) - 0.02, pill(spec["caption"]), "pill"))

# ------------------------------------------------------------------ render
MIC = (1074 / 1920 * SW, 14 / 1080 * SH)
BAR_VIEW = (MIC[0], 0, SW / MAX_ZOOM)
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                        "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                        "-pix_fmt", "yuv420p", str(D / "video.mp4")], stdin=subprocess.PIPE)
idx, last_out, last_src, end_bg = 0, None, None, None
XF = 0.12
for n in range(int(TOTAL * FPS)):
    t = n / FPS
    while idx + 1 < len(segs) and t >= segs[idx + 1]["start"]:
        idx += 1
    sg = segs[idx]
    local = t - sg["start"]
    if sg["kind"] == "hook":
        frame = hook_frame(local)
    elif sg["kind"] == "install":
        frame = install_frame(local)
    elif sg["kind"] == "end":
        end_bg = end_bg or card_bg(last_src)
        frame = end_frame(local, end_bg)
    else:
        src = raw_at(sg["a"] + local)
        if sg["view"] == "bar":
            L = sg["len"]
            k = ease_io(local / 0.45) if local < 0.45 else (1 - ease_io((local - L + 0.4) / 0.4) if local > L - 0.4 else 1)
            view = lerp_view(FULL, BAR_VIEW, k)
        else:
            step_t = t - step_start(sg["step"])
            k = ease(step_t / 0.4) if sg.get("first") else 1
            view = lerp_view(sg["from"], sg["view"], k)
            view = (view[0], view[1], view[2] * (1 - 0.03 * min(step_t / 3.0, 1)))
        frame, (x0, y0, s) = render_view(src, view)
        if sg["view"] == "bar" and 0.25 < local < sg["len"] - 0.3:
            phase = (local * 1.8) % 1
            ring = frame.copy()
            p = (int((MIC[0] - x0) * s), int((MIC[1] - y0) * s))
            cv2.circle(ring, p, int(s * PX * (9 + 6 * phase)), ACCENT[::-1], max(2, int(s * PX * 1.4)), cv2.LINE_AA)
            frame = cv2.addWeighted(frame, 1 - 0.9 * (1 - phase), ring, 0.9 * (1 - phase), 0)
        last_src = src
    if sg.get("xfade", sg["kind"] != "footage") and local < XF and last_out is not None and idx > 0:
        frame = cv2.addWeighted(last_out, 1 - local / XF, frame, local / XF, 0)
    for c0, c1, layer, kind in captions:
        if c0 <= t <= c1:
            alpha = min(1.0, (t - c0) / 0.09, (c1 - t) / 0.09)
            frame = overlay(frame, layer, alpha, 0.93 + 0.07 * ease((t - c0) / 0.13) if kind == "pill" else 1.0)
    if idx + 1 < len(segs) and t + 1 / FPS >= segs[idx + 1]["start"]:
        last_out = frame.copy()
    enc.stdin.write(np.ascontiguousarray(frame).tobytes())
enc.stdin.close()
enc.wait()

# ------------------------------------------------------------------ audio
inputs, filters, labels = [], [], []


def place(name, at, gain=1.0):
    k = len(inputs) // 2
    inputs.extend(["-i", str(D / "audio" / f"{name}.wav")])
    ms = max(0, int(at * 1000))
    filters.append(f"[{k}:a]aresample=48000,volume={gain},adelay={ms}|{ms}[a{k}]")
    labels.append(f"[a{k}]")


place("hook", 0.15)
place("intro", intro_seg["start"] + 0.05)
for i in USED:
    spec = script["steps"][i - 1]
    if spec.get("narration"):
        place(f"n{i:02d}", step_start(i) + 0.03)
    place(f"c{i:02d}", out_of(i, steps[i]["command_at"] + PLAY_LAG), 0.9)
place("install", segs[-2]["start"] + 0.1)
place("outro", segs[-1]["start"] + 0.2)
mix = ";".join(filters) + ";" + "".join(labels) + \
    f"amix=inputs={len(labels)}:normalize=0,apad,atrim=0:{TOTAL:.3f},loudnorm=I=-15:TP=-1.5:LRA=11[out]"
subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", mix, "-map", "[out]", "-ac", "2", "-ar", "48000",
                str(D / "audio_mix.wav")], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(D / "video.mp4"), "-i", str(D / "audio_mix.wav"), "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT)], check=True)
print(f"{OUT}  {TOTAL:.1f}s  from {SW}x{SH}")
