#!/usr/bin/env python3
"""Runs inside the VM: record the screen at native resolution while command
clips play into a virtual mic, leaving gaps for narration. Writes
timeline.json (seconds since recording started) and restores everything."""
import json, subprocess, sys, threading, time
from pathlib import Path

here = Path(__file__).parent
take = sys.argv[1] if len(sys.argv) > 1 else "take"
out = Path(f"/tmp/{take}.mp4")
script = json.loads((here / "script.json").read_text())
durations = json.loads((here / "durations.json").read_text())
conf = Path.home() / ".config/handsfree/config.toml"
profile = here / "ffprofile"


def sh(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True).stdout.strip()


def point_at_browser():
    """Park the pointer over Firefox so scrolling lands on the page."""
    clients = json.loads(sh("hyprctl -j clients") or "[]")
    for c in clients:
        if c.get("class", "").lower() == "firefox":
            x = c["at"][0] + c["size"][0] // 2
            y = c["at"][1] + int(c["size"][1] * 0.6)
            sh(f"""hyprctl dispatch 'hl.dsp.cursor.move({{ x = {x}, y = {y} }})'""")
            return


orig_source = sh("pactl get-default-source")
orig_theme = sh("omarchy-theme-current")
sink = sh("pactl load-module module-null-sink sink_name=hf_demo sink_properties=device.description=HandsfreeDemo")
mic = sh("pactl load-module module-remap-source master=hf_demo.monitor source_name=hf_demo_mic")
backup = conf.read_text()
recorder = None
parts = []  # wf-recorder dies when a theme switch reloads the desktop; keep restarting it
stop_recording = threading.Event()


def start_part(t0):
    path = Path(f"/tmp/{take}-part{len(parts)}.mp4")
    path.unlink(missing_ok=True)
    proc = subprocess.Popen(
        # gpu-screen-recorder survives Omarchy theme switches; wf-recorder dies, and
        # restarted mid-switch it captures at the wrong scale.
        ["gpu-screen-recorder", "-w", "screen", "-f", "30", "-k", "h264", "-encoder", "cpu", "-q", "very_high",
         "-o", str(path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    parts.append({"path": str(path), "start": time.monotonic() - t0})
    return proc


def supervise(t0):
    global recorder
    while not stop_recording.is_set():
        if recorder.poll() is not None:
            recorder = start_part(t0)
        time.sleep(0.05)


try:
    conf.write_text(backup + '\n[voice]\ninput_device = "pulse:hf_demo_mic"\n'
                    f'\n[desktop]\nurl_opener = ["firefox", "--profile", "{profile}"]\n')
    sh("pkill -x firefox; sleep 1")
    sh(f"rm -rf {profile}/sessionstore.jsonlz4 {profile}/sessionstore-backups {profile}/sessionCheckpoints.json")
    sh("""hyprctl dispatch 'hl.dsp.focus({ workspace = "1" })'""")
    sh("hyprctl dispatch 'hl.dsp.cursor.move({ x = 700, y = 420 })'")
    sh("systemctl --user restart handsfree; sleep 6")
    sh("handsfree-ctl dictation off; handsfree-ctl say close grid")
    t0 = time.monotonic()
    recorder = start_part(t0)
    threading.Thread(target=supervise, args=(t0,), daemon=True).start()
    time.sleep(1.2)
    listen_at = time.monotonic() - t0
    sh("handsfree-ctl voice on")
    time.sleep(1.3)
    monitor = next(m for m in json.loads(sh("hyprctl -j monitors")) if m.get("focused"))
    timeline = {"listen_at": listen_at, "steps": [], "monitor": {k: monitor[k] for k in ("width", "height", "scale")}}
    for i, step in enumerate(script["steps"], 1):
        narr_at = None
        if step.get("narration"):
            narr_at = time.monotonic() - t0
            time.sleep(durations[f"n{i:02d}"] + 0.35)
        at = time.monotonic() - t0
        subprocess.run(["paplay", "--device=hf_demo", str(here / "audio" / f"c{i:02d}.wav")])
        end = time.monotonic() - t0
        time.sleep(step["settle"])
        window = json.loads(sh("hyprctl -j activewindow") or "{}")
        if step.get("after") == "point_at_browser":
            point_at_browser()
        timeline["steps"].append({"step": i, "narration_at": narr_at, "command_at": at, "command_end": end,
                                  "window": {k: window.get(k) for k in ("class", "at", "size")} if window else None})
    time.sleep(0.6)
    timeline["end"] = time.monotonic() - t0
    stop_recording.set()
    time.sleep(0.1)
    timeline["parts"] = parts
    (here / "timeline.json").write_text(json.dumps(timeline, indent=1))
finally:
    stop_recording.set()
    if recorder:
        recorder.send_signal(2)
        try:  # a native-resolution encode can take a while to flush; never skip the restore below
            recorder.wait(timeout=180)
        except subprocess.TimeoutExpired:
            recorder.kill()
    sh("handsfree-ctl voice off")
    conf.write_text(backup)
    sh("systemctl --user restart handsfree")
    sh(f"pactl set-default-source {orig_source}; pactl unload-module {mic}; pactl unload-module {sink}")
    if orig_theme and sh("omarchy-theme-current") != orig_theme:
        sh(f'omarchy-theme-set "{orig_theme}"')
    sh("pkill -x firefox")
print(json.dumps(parts))
