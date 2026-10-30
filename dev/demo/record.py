#!/usr/bin/env python3
"""Runs inside the VM: record the screen while command clips play into a
virtual mic, leaving silent gaps where the narration will go. Writes
timeline.json with when each command clip started (seconds since recording)."""
import json, os, subprocess, sys, time
from pathlib import Path

here = Path(__file__).parent
take = sys.argv[1] if len(sys.argv) > 1 else "take"
out = Path(f"/tmp/{take}.mp4")
script = json.loads((here / "script.json").read_text())
durations = json.loads((here / "durations.json").read_text())
conf = Path.home() / ".config/handsfree/config.toml"
profile = here / "ffprofile"

def sh(cmd, check=False):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True, check=check).stdout.strip()

orig_source = sh("pactl get-default-source")
sink = sh("pactl load-module module-null-sink sink_name=hf_demo sink_properties=device.description=HandsfreeDemo")
mic = sh("pactl load-module module-remap-source master=hf_demo.monitor source_name=hf_demo_mic")
backup = conf.read_text()
recorder = None
try:
    conf.write_text(backup + f'\n[voice]\ninput_device = "pulse:hf_demo_mic"\n'
                    f'\n[desktop]\nurl_opener = ["firefox", "--profile", "{profile}"]\n')
    sh("pkill -x firefox; sleep 1")
    # A killed Firefox offers to restore tabs on next start; drop that state.
    sh(f"rm -rf {profile}/sessionstore.jsonlz4 {profile}/sessionstore-backups {profile}/sessionCheckpoints.json")
    sh("""hyprctl dispatch 'hl.dsp.focus({ workspace = "1" })'""")
    sh("systemctl --user restart handsfree; sleep 6")
    sh("handsfree-ctl dictation off; handsfree-ctl say close grid")
    out.unlink(missing_ok=True)
    recorder = subprocess.Popen(
        ["wf-recorder", "-y", "-a=hf_demo.monitor", "-r", "30", "-F", "scale=1920:-2",
         "-c", "libx264", "-p", "preset=veryfast", "-p", "crf=18", "-f", str(out)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.monotonic()
    time.sleep(1.5)
    sh("handsfree-ctl voice on")
    time.sleep(1.0)
    timeline = []
    for i, step in enumerate(script["steps"], 1):
        if step.get("narration"):
            narr_at = time.monotonic() - t0
            time.sleep(durations[f"n{i:02d}"] + 0.5)
        else:
            narr_at = None
        at = time.monotonic() - t0
        subprocess.run(["paplay", "--device=hf_demo", str(here / "audio" / f"c{i:02d}.wav")])
        timeline.append({"step": i, "narration_at": narr_at, "command_at": at,
                         "command_end": time.monotonic() - t0})
        time.sleep(step["settle"])
    time.sleep(0.5)
    (here / "timeline.json").write_text(json.dumps(timeline, indent=1))
finally:
    if recorder:
        recorder.send_signal(2); recorder.wait(timeout=15)
    sh("handsfree-ctl voice off")
    conf.write_text(backup)
    sh("systemctl --user restart handsfree")
    sh(f"pactl set-default-source {orig_source}; pactl unload-module {mic}; pactl unload-module {sink}")
print(out, out.stat().st_size if out.exists() else "missing")
