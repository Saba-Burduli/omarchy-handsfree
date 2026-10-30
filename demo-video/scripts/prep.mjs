// Turn a recorded take into what the Remotion edit needs:
//   public/take/screen.mp4  the footage (with the voice as its audio track)
//   public/music.mp3        copied from ./music.mp3 if present
//   src/take.json           steps (clip + log entry), sync offset, voice envelope, music beats
//
//   node scripts/prep.mjs [takes/<name>]   (default: newest take)
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { fileURLToPath } from "node:url";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const takes = path.join(root, "takes");
const takeDir = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(takes, fs.readdirSync(takes).filter((d) => !d.startsWith(".")).sort().at(-1));
const FPS = 60; // envelope resolution

const jsonl = (f) =>
  fs.readFileSync(path.join(takeDir, f), "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
const meta = JSON.parse(fs.readFileSync(path.join(takeDir, "meta.json"), "utf8"));
const clips = jsonl("clips.jsonl");
const log = jsonl("log.jsonl");
const parts = jsonl("parts.jsonl");
if (parts.length > 1) console.warn("recorder restarted mid-take; only screen-0.mp4 is used");
const screen = path.join(takeDir, "screen-0.mp4");

// Mono float PCM of any media file.
function pcm(file, rate) {
  const buf = execFileSync("ffmpeg", ["-loglevel", "error", "-i", file, "-vn", "-ac", "1", "-ar", String(rate), "-f", "f32le", "-"], {
    maxBuffer: 1 << 30,
  });
  return new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4);
}

// -- voice envelope, one RMS value per frame ----------------------------------
const RATE = 48000;
const voice = pcm(screen, RATE);
const hop = RATE / FPS;
const envelope = [];
for (let i = 0; i + hop <= voice.length; i += hop) {
  let s = 0;
  for (let j = i; j < i + hop; j++) s += voice[j] * voice[j];
  envelope.push(Math.sqrt(s / hop));
}
const peak = Math.max(...envelope) || 1;
const env = envelope.map((v) => Math.round((v / peak) * 1000) / 1000);

// Where the voice actually starts near each clip, to measure recorder lag.
const onset = (from, to) => {
  for (let f = Math.max(0, Math.floor(from * FPS)); f < Math.min(env.length, to * FPS); f++) if (env[f] > 0.05) return f / FPS;
  return null;
};
function leadingSilence(file) {
  const a = pcm(file, 16000);
  const i = a.findIndex((v) => Math.abs(v) > 0.02);
  return i < 0 ? 0 : i / 16000;
}
const lags = clips
  .map((c) => {
    const o = onset(c.start - 0.3, c.end + 0.3);
    const clipFile = path.join(root, c.clip);
    return o === null || !fs.existsSync(clipFile) ? null : o - (c.start + leadingSilence(clipFile));
  })
  .filter((v) => v !== null)
  .sort((a, b) => a - b);
const offset = lags.length ? lags[Math.floor(lags.length / 2)] : 0; // log time + offset = video time

// -- the moment each result shows on screen ------------------------------------
function changeTime(from, dur) {
  // showinfo prints each frame that differs from the one before (on stderr).
  const { stderr } = spawnSync(
    "ffmpeg",
    ["-hide_banner", "-ss", from.toFixed(3), "-t", String(dur), "-i", screen, "-an", "-vf", "scale=480:-2,select='gt(scene\\,0.004)',showinfo", "-f", "null", "-"],
    { encoding: "utf8" },
  );
  const m = /pts_time:([\d.]+)/.exec(stderr);
  return m ? from + parseFloat(m[1]) : null;
}

const mon = meta.monitor;
const rect = (w) =>
  w && {
    x: (w.x - mon.x) * mon.scale,
    y: (w.y - mon.y) * mon.scale,
    w: w.w * mon.scale,
    h: w.h * mon.scale,
    cls: w.class,
  };

const steps = clips.map((c, i) => {
  const next = clips[i + 1]?.start ?? Infinity;
  const entry = log.find((e) => e.t >= c.start - 0.05 && e.t < next);
  const t = entry ? entry.t + offset : null;
  const visible = t === null ? null : changeTime(t, Math.min(3, (next === Infinity ? t + 3 : next + offset) - t));
  return {
    n: c.n,
    words: c.words,
    heard: (entry?.heard ?? "").replace(/[.!?]+$/, ""),
    action: entry?.action ?? null,
    ok: Boolean(entry?.ok),
    speechStart: c.start + offset,
    speechEnd: c.end + offset,
    t,
    visible: visible ?? t, // first frame that changed after the action
    done: entry ? entry.t_done + offset : null,
    window: rect(entry?.window),
  };
});

// -- music beats (optional) ----------------------------------------------------
let beats = null;
const music = path.join(root, "music.mp3");
fs.mkdirSync(path.join(root, "public", "take"), { recursive: true });
if (fs.existsSync(music)) {
  fs.copyFileSync(music, path.join(root, "public", "music.mp3"));
  const mrate = 22050;
  const m = pcm(music, mrate);
  const h = 512;
  const energy = [];
  for (let i = 0; i + h <= m.length; i += h) {
    let s = 0;
    for (let j = i; j < i + h; j++) s += m[j] * m[j];
    energy.push(Math.log1p(s));
  }
  const flux = energy.map((e, i) => Math.max(0, e - (energy[i - 1] ?? e)));
  const W = 20;
  beats = [];
  let last = -1;
  for (let i = W; i < flux.length - W; i++) {
    const win = flux.slice(i - W, i + W);
    const mean = win.reduce((a, b) => a + b, 0) / win.length;
    const t = (i * h) / mrate;
    if (flux[i] === Math.max(...win) && flux[i] > mean * 1.8 && t - last > 0.25) {
      beats.push(Math.round(t * 1000) / 1000);
      last = t;
    }
  }
} else {
  fs.rmSync(path.join(root, "public", "music.mp3"), { force: true });
}

fs.copyFileSync(screen, path.join(root, "public", "take", "screen.mp4"));
const duration = parseFloat(
  execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", screen], { encoding: "utf8" }),
);
const out = {
  take: path.basename(takeDir),
  source: { width: 3456, height: 1944, duration, monitor: mon },
  offset: Math.round(offset * 1000) / 1000,
  steps,
  envelopeFps: FPS,
  envelope: env,
  beats,
};
const probe = execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", screen], {
  encoding: "utf8",
}).trim();
[out.source.width, out.source.height] = probe.split(",").map(Number);
fs.writeFileSync(path.join(root, "src", "take.json"), JSON.stringify(out));
console.log(`take ${out.take}: ${steps.length} steps, offset ${out.offset}s, ${beats ? beats.length + " beats" : "no music"}`);
for (const s of steps)
  console.log(`${s.n} ${s.ok ? "ok " : "MISS"} "${s.heard}" t=${s.t?.toFixed(2)} visible=${s.visible?.toFixed(2)} ${s.window ? s.window.cls : "-"}`);
