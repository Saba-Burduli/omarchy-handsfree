"""Edit the raw take into the launch video: title card, eased zooms, captions,
a cut, an end card, and a voiceover + command-voice soundtrack."""

import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

D = Path(sys.argv[1])
RAW = D / "raw2.mp4"
OUT = Path(sys.argv[2])
W, H, FPS = 1920, 1080, 30
script = json.loads((D / "script.json").read_text())
durations = json.loads((D / "durations.json").read_text())
timeline = {s["step"]: s for s in json.loads((D / "timeline.json").read_text())}
PLAY_LAG = 0.08  # paplay starts this long after the logged time

# ---------------------------------------------------------------- timeline
TITLE = 2.4            # title card
SLOW = (0.6, 2.55)     # raw span stretched under the intro narration
SLOW_END = 6.6         # output time the stretched span ends
CUT = (22.14, 26.2)    # raw span removed ("scroll down" didn't move anything)
RAW_END = 59.3
END_CARD = 7.0
XFADE = 0.3

seg2_out = SLOW_END
seg3_out = seg2_out + (CUT[0] - SLOW[1])
footage_end = seg3_out + (RAW_END - CUT[1])
TOTAL = footage_end + END_CARD


def raw_to_out(t: float) -> float:
    if t < SLOW[1]:
        return TITLE + (t - SLOW[0]) / (SLOW[1] - SLOW[0]) * (SLOW_END - TITLE)
    if t < CUT[0]:
        return seg2_out + (t - SLOW[1])
    if t < CUT[1]:
        return seg3_out  # inside the removed span
    return seg3_out + (t - CUT[1])


def out_to_raw(t: float) -> float | None:
    if t < TITLE or t >= footage_end:
        return None
    if t < SLOW_END:
        return SLOW[0] + (t - TITLE) / (SLOW_END - TITLE) * (SLOW[1] - SLOW[0])
    if t < seg3_out:
        return SLOW[1] + (t - seg2_out)
    return CUT[1] + (t - seg3_out)


# ---------------------------------------------------------------- zoom path
FULL = (960, 540, 1920)
FIREFOX = (987, 549, 1300)
SEARCH = (987, 470, 1000)
BAR = (1074, 120, 560)
MIC_ICON = (1074, 14)  # the bar's microphone indicator, raw coordinates
GRID5 = (960, 540, 780)

# (raw time, view) keyframes; views ease between consecutive keyframes
KEYS = [
    (0.0, FULL), (0.9, FULL), (1.5, BAR), (2.35, BAR), (3.0, FULL),
    (7.9, FULL), (8.9, FIREFOX), (14.4, FIREFOX), (15.1, SEARCH), (17.9, SEARCH),
    (18.7, FIREFOX), (22.2, FIREFOX), (26.4, FIREFOX), (27.5, FULL),
    (48.4, FULL), (49.2, GRID5), (51.4, GRID5), (52.2, FULL),
    (60.0, FULL),
]


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def view_at(t: float):
    for (t0, v0), (t1, v1) in zip(KEYS, KEYS[1:]):
        if t0 <= t <= t1:
            k = ease((t - t0) / (t1 - t0)) if t1 > t0 else 1
            # interpolate zoom in log space so it feels constant-speed
            w = math.exp(math.log(v0[2]) * (1 - k) + math.log(v1[2]) * k)
            return (v0[0] + (v1[0] - v0[0]) * k, v0[1] + (v1[1] - v0[1]) * k, w)
    return KEYS[-1][1]


def view_transform(view):
    cx, cy, w = view
    h = w * H / W
    x = min(max(cx - w / 2, 0), W - w)
    y = min(max(cy - h / 2, 0), H - h)
    return x, y, W / w


def apply_view(frame, view):
    x, y, s = view_transform(view)
    m = np.float32([[s, 0, -x * s], [0, s, -y * s]])
    return cv2.warpAffine(frame, m, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


# ---------------------------------------------------------------- type
def font(size: int, weight: str = "Bold"):
    f = ImageFont.truetype("/System/Library/Fonts/SFNS.ttf", size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


MONO = lambda size: ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", size)


def text_size(draw, text, f):
    l, t, r, b = draw.textbbox((0, 0), text, font=f)
    return r - l, b - t, l, t


def command_pill(text: str) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f, small = font(54, "Bold"), font(28, "Semibold")
    label = "YOU SAY"
    tw, th, tl, tt = text_size(d, f"“{text}”", f)
    lw, lh, ll, lt = text_size(d, label, small)
    pad_x, dot = 44, 22
    width = pad_x * 2 + dot + 22 + max(tw, lw)
    height = 150
    x0, y0 = (W - width) // 2, H - height - 70
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((x0, y0 + 10, x0 + width, y0 + height + 10), 40, fill=(0, 0, 0, 120))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    d.rounded_rectangle((x0, y0, x0 + width, y0 + height), 40, fill=(18, 20, 24, 235), outline=(255, 255, 255, 40), width=2)
    cx = x0 + pad_x + dot // 2
    d.ellipse((cx - dot // 2, y0 + 70 - dot // 2, cx + dot // 2, y0 + 70 + dot // 2), fill=(239, 68, 68, 255))
    tx = x0 + pad_x + dot + 22
    d.text((tx - ll, y0 + 26 - lt), label, font=small, fill=(239, 68, 68, 255))
    d.text((tx - tl, y0 + 62 - tt), f"“{text}”", font=f, fill=(255, 255, 255, 255))
    return img


def subtitle(text: str) -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(40, "Semibold")
    tw, th, tl, tt = text_size(d, text, f)
    x0, y0 = (W - tw) // 2, H - 150
    d.rounded_rectangle((x0 - 30, y0 - 22, x0 + tw + 30, y0 + th + 26), 18, fill=(0, 0, 0, 150))
    d.text((x0 - tl, y0 - tt), text, font=f, fill=(255, 255, 255, 245))
    return img


def card_background(frame) -> Image.Image:
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).filter(ImageFilter.GaussianBlur(28))
    dark = Image.new("RGB", (W, H), (10, 12, 16))
    return Image.blend(img, dark, 0.62).convert("RGBA")


def title_layer() -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lines = [
        ("Omarchy Hands-free", font(120, "Bold"), (255, 255, 255, 255), 0),
        ("Control your desktop with your voice.", font(48, "Medium"), (220, 224, 230, 255), 40),
        ("Offline  ·  Open source  ·  Built for Omarchy", font(32, "Semibold"), (239, 68, 68, 255), 34),
    ]
    heights = [text_size(d, t, f)[1] for t, f, _, _ in lines]
    y = (H - sum(heights) - sum(g for *_, g in lines)) // 2 - 30
    for (t, f, c, gap), h in zip(lines, heights):
        w, _, l, top = text_size(d, t, f)
        y += gap
        d.text(((W - w) // 2 - l, y - top), t, font=f, fill=c)
        y += h
    return img


def end_layer() -> Image.Image:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rows = [
        ("Omarchy Hands-free", font(104, "Bold"), (255, 255, 255, 255)),
        ("Voice and eye control for Omarchy. Free and open source.", font(42, "Medium"), (220, 224, 230, 255)),
    ]
    y = 300
    for t, f, c in rows:
        w, h, l, top = text_size(d, t, f)
        d.text(((W - w) // 2 - l, y - top), t, font=f, fill=c)
        y += h + 46
    cmd = "github.com/Saba-Burduli/omarchy-handsfree"
    f = MONO(46)
    w, h, l, top = text_size(d, cmd, f)
    box = ((W - w) // 2 - 40, y + 30, (W + w) // 2 + 40, y + 30 + h + 60)
    d.rounded_rectangle(box, 22, fill=(18, 20, 24, 240), outline=(239, 68, 68, 200), width=3)
    d.text(((W - w) // 2 - l, y + 60 - top), cmd, font=f, fill=(255, 255, 255, 255))
    hint = "git clone, then ./install.sh"
    f2 = font(32, "Semibold")
    w2, h2, l2, t2 = text_size(d, hint, f2)
    d.text(((W - w2) // 2 - l2, box[3] + 40 - t2), hint, font=f2, fill=(170, 176, 186, 255))
    return img


# ---------------------------------------------------------------- overlays schedule (output times)
overlays = []  # (start, end, image)
intro_at = 0.35
overlays.append((TITLE + 0.2, SLOW_END - 0.15, subtitle("You talk, and Omarchy does it. Everything runs offline.")))
for i, step in enumerate(script["steps"], 1):
    s = timeline[i]
    if s["command_at"] > CUT[0] and s["command_at"] < CUT[1]:
        continue  # cut
    if step.get("narration"):
        n0 = raw_to_out(s["narration_at"])
        overlays.append((n0 + 0.05, n0 + durations[f"n{i:02d}"] + 0.25, subtitle(step["narration"])))
    c0 = raw_to_out(s["command_at"] + PLAY_LAG)
    nxt = timeline.get(i + 1)
    limit = raw_to_out(nxt["narration_at"] or nxt["command_at"]) - 0.1 if nxt else footage_end - 0.2
    if nxt and CUT[0] < nxt["command_at"] < CUT[1]:
        nn = timeline.get(i + 2)
        limit = min(limit, raw_to_out(CUT[0]) - 0.1)
    overlays.append((c0, min(raw_to_out(s["command_end"]) + 1.6, limit), command_pill(step["caption"])))


def alpha_for(t, start, end, fade=0.18):
    if t < start or t > end:
        return 0.0
    return min(1.0, (t - start) / fade, (end - t) / fade)


def blend(base: np.ndarray, layer: Image.Image, alpha: float) -> np.ndarray:
    if alpha <= 0:
        return base
    rgba = np.asarray(layer, dtype=np.float32)
    a = rgba[..., 3:4] / 255.0 * alpha
    rgb = rgba[..., :3][..., ::-1]  # to BGR
    return (base * (1 - a) + rgb * a).astype(np.uint8)


# ---------------------------------------------------------------- render
cap = cv2.VideoCapture(str(RAW))
raw_fps = cap.get(cv2.CAP_PROP_FPS) or 30
raw_index, raw_frame = -1, None


def raw_at(t: float):
    global raw_index, raw_frame
    want = int(round(t * raw_fps))
    while raw_index < want:
        ok, f = cap.read()
        if not ok:
            break
        raw_index += 1
        if f.shape[1] != W:
            f = cv2.resize(f, (W, H), interpolation=cv2.INTER_AREA)
        raw_frame = f
    return raw_frame


# Card backgrounds from real frames (desktop at the start, last frame at the end).
first = raw_at(1.0)
title_bg = card_background(first)
title_fg = title_layer()
end_fg = end_layer()

enc = subprocess.Popen(
    ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
     "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", str(D / "video.mp4")],
    stdin=subprocess.PIPE)

title_np = cv2.cvtColor(np.asarray(Image.alpha_composite(title_bg, title_fg).convert("RGB")), cv2.COLOR_RGB2BGR)
title_bg_np = cv2.cvtColor(np.asarray(title_bg.convert("RGB")), cv2.COLOR_RGB2BGR)
last_footage = None
cut_from = None
end_np = None
n_frames = int(TOTAL * FPS)
for n in range(n_frames):
    t = n / FPS
    raw_t = out_to_raw(t)
    if raw_t is None and t < TITLE:
        # title card: gentle push-in and fade-in of the text
        k = ease(t / 0.6)
        view = (960, 540, W / (1.0 + 0.03 * t / TITLE))  # slow push-in
        frame = cv2.addWeighted(apply_view(title_bg_np, view), 1 - k, apply_view(title_np, view), k, 0)
    elif raw_t is not None:
        src = raw_at(raw_t)
        view = view_at(raw_t)
        frame = apply_view(src, view)
        if 1.45 <= raw_t <= 2.5:  # pulse a ring around the mic icon as listening turns on
            x, y, s = view_transform(view)
            px, py = int((MIC_ICON[0] - x) * s), int((MIC_ICON[1] - y) * s)
            phase = (raw_t - 1.45) * 2.2
            radius = int(s * (9 + 6 * (phase % 1)))
            ring = frame.copy()
            cv2.circle(ring, (px, py), radius, (68, 68, 239), max(2, int(s * 1.6)), cv2.LINE_AA)
            fade = min(1.0, (raw_t - 1.45) / 0.15, (2.5 - raw_t) / 0.15) * (1 - 0.6 * (phase % 1))
            frame = cv2.addWeighted(frame, 1 - fade, ring, fade, 0)
        # crossfade into the footage after the title
        if t < TITLE + XFADE:
            k = (t - TITLE) / XFADE
            frame = cv2.addWeighted(apply_view(title_np, (960, 540, W / 1.03)), 1 - k, frame, k, 0)
        # crossfade across the cut
        if seg3_out <= t < seg3_out + XFADE and cut_from is not None:
            k = (t - seg3_out) / XFADE
            frame = cv2.addWeighted(cut_from, 1 - k, frame, k, 0)
        if t < seg3_out:
            cut_from = frame.copy()
        last_footage = frame
    else:
        if end_np is None:
            end_bg = card_background(last_footage)
            end_np = cv2.cvtColor(np.asarray(Image.alpha_composite(end_bg, end_fg).convert("RGB")), cv2.COLOR_RGB2BGR)
        k = ease((t - footage_end) / 0.6)
        frame = cv2.addWeighted(last_footage, 1 - k, end_np, k, 0)
    for start, end, layer in overlays:
        a = alpha_for(t, start, end)
        if a:
            frame = blend(frame.astype(np.float32), layer, a)
    enc.stdin.write(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())
enc.stdin.close()
enc.wait()

# ---------------------------------------------------------------- audio
inputs, filters, labels = [], [], []


def place(path: Path, at: float, gain: float):
    k = len(inputs) // 2
    inputs.extend(["-i", str(path)])
    ms = max(0, int(at * 1000))
    filters.append(f"[{k}:a]aresample=48000,volume={gain},adelay={ms}|{ms}[a{k}]")
    labels.append(f"[a{k}]")


place(D / "audio" / "intro.wav", intro_at, 1.0)
for i, step in enumerate(script["steps"], 1):
    s = timeline[i]
    if CUT[0] < s["command_at"] < CUT[1]:
        continue
    if step.get("narration"):
        place(D / "audio" / f"n{i:02d}.wav", raw_to_out(s["narration_at"]), 1.0)
    place(D / "audio" / f"c{i:02d}.wav", raw_to_out(s["command_at"] + PLAY_LAG), 0.95)
place(D / "audio" / "outro.wav", footage_end + 0.5, 1.0)
mix = ";".join(filters) + ";" + "".join(labels) + \
    f"amix=inputs={len(labels)}:normalize=0,apad,atrim=0:{TOTAL:.3f},loudnorm=I=-16:TP=-1.5:LRA=11[out]"
subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", mix, "-map", "[out]",
                "-ac", "2", "-ar", "48000", str(D / "audio.wav")], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(D / "video.mp4"), "-i", str(D / "audio.wav"),
                "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(OUT)],
               check=True)
print(f"{OUT}  {TOTAL:.1f}s")
