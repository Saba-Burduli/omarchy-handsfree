// ElevenLabs audio for the demo. The key is read from ~/.config/elevenlabs.env
// (ELEVENLABS_API_KEY=...). Existing files are kept unless --force.
//
//   node scripts/elevenlabs.mjs commands   voice/NN.wav from commands.txt (played into the mic)
//   node scripts/elevenlabs.mjs narration  public/vo/<id>.mp3 from narration.json, durations in src/vo.json
//   node scripts/elevenlabs.mjs sfx        public/sfx/<id>.mp3
//   node scripts/elevenlabs.mjs music      music.mp3 (needs a plan with music access)
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const [what, ...flags] = process.argv.slice(2);
const force = flags.includes("--force");

const VOICES = {
  commands: process.env.COMMAND_VOICE ?? "EXAVITQu4vr4xnSDxMaL", // Sarah
  narrator: process.env.NARRATOR_VOICE ?? "TX3LPaxmHKxFdv7VOQHJ", // Liam
};
const SFX = [
  { id: "pop", seconds: 0.5, text: "soft short UI pop, a clean bubble pop for an app notification" },
  { id: "ding", seconds: 0.7, text: "subtle bright two-note success chime, modern UI confirmation sound" },
  { id: "whoosh", seconds: 0.8, text: "fast smooth airy whoosh transition, clean swoosh" },
  { id: "hit", seconds: 2.0, text: "deep cinematic logo reveal hit with a soft shimmering reverb tail" },
];
const MUSIC =
  "Upbeat modern electronic background music for a tech product demo video. Driving punchy beat around 118 BPM, " +
  "warm synth bass, bright plucks, confident and energetic, minimal, no vocals.";

const LOOP =
  "Seamless loop of upbeat modern electronic music for a tech demo, punchy four-on-the-floor drums at 120 BPM, " +
  "warm synth bass line, bright plucked synth chords, energetic and clean, no vocals.";

const env = fs.readFileSync(path.join(os.homedir(), ".config/elevenlabs.env"), "utf8");
const key = env.match(/ELEVENLABS_API_KEY=\s*"?([^"\s]+)/)?.[1];
if (!key) throw new Error("ELEVENLABS_API_KEY missing from ~/.config/elevenlabs.env");

async function post(endpoint, body) {
  const r = await fetch(`https://api.elevenlabs.io${endpoint}`, {
    method: "POST",
    headers: { "xi-api-key": key, "content-type": "application/json", accept: "audio/mpeg" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${endpoint}: ${r.status} ${(await r.text()).slice(0, 300)}`);
  return Buffer.from(await r.arrayBuffer());
}

const tts = (voice, text, settings) =>
  post(`/v1/text-to-speech/${voice}?output_format=mp3_44100_128`, {
    text,
    model_id: "eleven_multilingual_v2",
    voice_settings: { stability: 0.5, similarity_boost: 0.8, style: 0.3, use_speaker_boost: true, ...settings },
  });

const duration = (file) =>
  parseFloat(execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file], { encoding: "utf8" }));
const skip = (file) => !force && fs.existsSync(file);

if (what === "commands") {
  fs.mkdirSync(path.join(root, "voice"), { recursive: true });
  for (const line of fs.readFileSync(path.join(root, "commands.txt"), "utf8").split("\n")) {
    if (!line.trim() || line.startsWith("#")) continue;
    const [n, words] = line.split("|");
    const out = path.join(root, "voice", `${n}.wav`);
    if (skip(out)) continue;
    // Spoken like a person giving a command: capitalized, ending in a period.
    const mp3 = await tts(VOICES.commands, words[0].toUpperCase() + words.slice(1) + ".", { stability: 0.6, style: 0.15 });
    const tmp = path.join(os.tmpdir(), `hf-${n}.mp3`);
    fs.writeFileSync(tmp, mp3);
    execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-i", tmp, "-ar", "48000", "-ac", "1", out]);
    fs.rmSync(tmp);
    console.log(`${n}  ${words}  ${duration(out).toFixed(2)}s`);
  }
} else if (what === "narration") {
  const lines = JSON.parse(fs.readFileSync(path.join(root, "narration.json"), "utf8"));
  const dir = path.join(root, "public", "vo");
  fs.mkdirSync(dir, { recursive: true });
  const durations = {};
  for (const [id, text] of Object.entries(lines)) {
    const out = path.join(dir, `${id}.mp3`);
    if (!skip(out)) fs.writeFileSync(out, await tts(VOICES.narrator, text, { stability: 0.45, style: 0.45 }));
    durations[id] = Math.round(duration(out) * 1000) / 1000;
    console.log(`${id}  ${durations[id]}s  ${text}`);
  }
  fs.writeFileSync(path.join(root, "src", "vo.json"), JSON.stringify(durations, null, 1));
} else if (what === "sfx") {
  const dir = path.join(root, "public", "sfx");
  fs.mkdirSync(dir, { recursive: true });
  for (const s of SFX) {
    const out = path.join(dir, `${s.id}.mp3`);
    if (skip(out)) continue;
    fs.writeFileSync(out, await post("/v1/sound-generation", { text: s.text, duration_seconds: s.seconds, prompt_influence: 0.5 }));
    console.log(`${s.id}  ${duration(out).toFixed(2)}s`);
  }
} else if (what === "music") {
  // The Music API needs a paid plan; on free, a seamless sound-effects loop repeated works as a bed.
  const out = path.join(root, "music.mp3");
  if (!skip(out)) {
    try {
      fs.writeFileSync(out, await post("/v1/music", { prompt: MUSIC, music_length_ms: 80000 }));
    } catch (e) {
      if (!String(e).includes("402")) throw e;
      const loop = path.join(os.tmpdir(), "hf-loop.mp3");
      fs.writeFileSync(loop, await post("/v1/sound-generation", {
        text: LOOP, duration_seconds: 20, loop: true, prompt_influence: 0.6, model_id: "eleven_text_to_sound_v2",
      }));
      execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-stream_loop", "4", "-i", loop, "-c:a", "libmp3lame", "-q:a", "2", out]);
      fs.rmSync(loop);
    }
  }
  console.log(`music.mp3  ${duration(out).toFixed(1)}s`);
} else {
  console.error("usage: node scripts/elevenlabs.mjs commands|narration|sfx|music [--force]");
  process.exit(2);
}
