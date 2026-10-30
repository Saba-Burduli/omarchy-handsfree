// The edit decision list, computed from the take: which source seconds play
// when, where the camera points, and when narration and sound effects play.
// Everything is in output frames.
import { config } from "./config";
import take from "./take.json";
import vo from "./vo.json";

export const FPS = 60;
export const SOURCE = { w: take.source.width, h: take.source.height };

export type Rect = { x: number; y: number; w: number; h: number };
export type Step = (typeof take.steps)[number];
export type Segment = { from: number; dur: number; src: number; muted: boolean }; // src in seconds
export type Kind = "hook" | "normal" | "fast";
export type Shot = {
  n: string;
  kind: Kind;
  heard: string;
  from: number;
  end: number;
  speech: Segment;
  action: Segment;
  before: Rect; // camera while the command is spoken
  rect: Rect; // camera once the result shows, from the command log
};
export type Cue = { src: string; from: number; volume: number };

const FULL: Rect = { x: 0, y: 0, w: SOURCE.w, h: SOURCE.h };
const sec = (s: number) => Math.round(s * FPS);
const voLen = (id: string) => (vo as Record<string, number>)[id] ?? 0;

// Seconds kept around the spoken command and after the result appears. The
// lead-in lets the pill show up before the words, so each command reads clearly.
const SPEECH_PRE: Record<Kind, number> = { hook: 0.15, normal: 0.4, fast: 0.3 };
const SPEECH_POST = 0.05;
const HOLD: Record<Kind, number> = { hook: 1.2, normal: 2.0, fast: 1.25 };
const MIN_HOLD = 0.6;
const OVERLAP = 12; // frames the intro/outro cards fade over the footage
export const OUTRO = sec(7.5);

const byN = new Map(take.steps.map((s) => [s.n, s]));
const pad = (r: Rect, k: number): Rect => ({ x: r.x - (r.w * k) / 2, y: r.y - (r.h * k) / 2, w: r.w * (1 + k), h: r.h * (1 + k) });

// The window the command log reported, padded a little. Whole-screen results
// (themes, the mouse grid, closed windows) frame the whole screen.
function target(step: Step | undefined): Rect {
  if (!step?.window || /theme|grid|zoomed into/.test(step.action ?? "")) return FULL;
  return pad(step.window, 0.08);
}

// What was on screen while a command was being said: the previous recorded result.
function before(step: Step): Rect {
  const prev = take.steps[take.steps.indexOf(step) - 1];
  return prev?.window ? pad(prev.window, 0.08) : FULL;
}

// With music, nudge a cut onto the nearest beat (by stretching the hold).
function snapToBeat(cut: number, holdStart: number): number {
  const beats = take.beats as number[] | null;
  if (!beats?.length) return cut;
  const near = beats.reduce((a, b) => (Math.abs(b - cut) < Math.abs(a - cut) ? b : a));
  return Math.abs(near - cut) <= 0.25 && near - holdStart >= MIN_HOLD ? near : cut;
}

function makeShot(n: string, kind: Kind, from: number): Shot {
  const step = byN.get(n);
  if (!step || step.visible === null) throw new Error(`clip ${n} has no logged result in take ${take.take}`);
  const speechStart = step.speechStart - SPEECH_PRE[kind];
  const speechDur = sec(step.speechEnd + SPEECH_POST - speechStart);
  // Cut straight from the end of the words to the result: the gap between is
  // handsfree waiting for silence, with nothing changing on screen.
  const actionSrc = step.visible - 0.08;
  const holdStart = (from + speechDur) / FPS;
  const end = snapToBeat(holdStart + HOLD[kind] + (config.hold[n] ?? 0), holdStart);
  const actionDur = sec(end) - from - speechDur;
  return {
    n,
    kind,
    heard: step.heard || step.words,
    from,
    end: from + speechDur + actionDur,
    // Only the spoken command is heard from the footage.
    speech: { from, dur: speechDur, src: speechStart, muted: false },
    action: { from: from + speechDur, dur: actionDur, src: actionSrc, muted: true },
    before: before(step),
    rect: target(step),
  };
}

// Make room for a narrator line at the end of a shot by holding its result
// longer. The screen stays as it is until the next command's result appears,
// so the extra footage is real, just quiet.
function stretchFor(shot: Shot, seconds: number) {
  // Only up to the next recorded command, even if the edit skips it.
  const nextStep = take.steps[take.steps.findIndex((s) => s.n === shot.n) + 1];
  const room = sec((nextStep?.visible ?? Infinity) - 0.2 - shot.action.src);
  const want = sec(seconds);
  const dur = Math.max(shot.action.dur, Math.min(want, room));
  shot.action.dur = dur;
  shot.end = shot.action.from + dur;
}

function build() {
  const shots: Shot[] = [];
  const voice: Cue[] = [];
  const sfx: Cue[] = [];
  const chips: { text: string; from: number }[] = [];

  const hook = makeShot(config.hook, "hook", 0);
  shots.push(hook);

  // Intro card: the narrator explains the project, then introduces the first section.
  const introFrom = hook.end - OVERLAP;
  const first = config.sections[config.order[0]];
  const introVo = introFrom + sec(0.25);
  voice.push({ src: "vo/intro.mp3", from: introVo, volume: 1 });
  let introEnd = introVo + sec(voLen("intro") + 0.3);
  if (first) {
    voice.push({ src: `vo/${first.vo}.mp3`, from: introEnd, volume: 1 });
    introEnd += sec(voLen(first.vo) + 0.25);
    chips.push({ text: first.label, from: introEnd });
  }
  sfx.push({ src: "sfx/whoosh.mp3", from: introFrom - 4, volume: 0.5 }, { src: "sfx/hit.mp3", from: introVo, volume: 0.55 });

  let cursor = introEnd;
  config.order.forEach((n, i) => {
    const kind: Kind = config.fast.includes(n) ? "fast" : "normal";
    const section = config.sections[n];
    if (section && i > 0) {
      // The line plays over the end of the previous result.
      const prev = shots[shots.length - 1];
      const len = voLen(section.vo);
      // A beat on the result first, then the line, ending just before the cut.
      stretchFor(prev, 0.6 + len + 0.35);
      const at = Math.max(prev.action.from + sec(0.6), prev.end - sec(len + 0.3));
      voice.push({ src: `vo/${section.vo}.mp3`, from: at, volume: 1 });
      chips.push({ text: section.label, from: at });
      sfx.push({ src: "sfx/whoosh.mp3", from: at - 6, volume: 0.35 });
      cursor = prev.end;
    }
    const shot = makeShot(n, kind, cursor);
    shots.push(shot);
    cursor = shot.end;
  });

  for (const s of shots) {
    sfx.push({ src: "sfx/pop.mp3", from: s.from + 2, volume: 0.3 }, { src: "sfx/ding.mp3", from: s.action.from, volume: 0.32 });
  }
  const outroFrom = cursor - OVERLAP;
  voice.push({ src: "vo/outro.mp3", from: outroFrom + sec(0.35), volume: 1 });
  sfx.push({ src: "sfx/whoosh.mp3", from: outroFrom - 4, volume: 0.5 }, { src: "sfx/hit.mp3", from: outroFrom + 6, volume: 0.45 });

  return { shots, voice, sfx, chips, introFrom, introDur: introEnd - introFrom + OVERLAP, outroFrom, total: outroFrom + OUTRO };
}

export const plan = build();
export const hasMusic = Array.isArray(take.beats);
export const envelope = take.envelope as number[];
export const envelopeFps = take.envelopeFps;

// Someone is talking (command or narrator): music dips under it.
export function speaking(frame: number) {
  return (
    plan.shots.some((s) => frame >= s.from && frame < s.action.from + 6) ||
    plan.voice.some((v) => frame >= v.from - 6 && frame < v.from + sec(voLen(v.src.slice(3, -4)) + 0.2))
  );
}

// -- camera ---------------------------------------------------------------------
export function lerpRect(a: Rect, b: Rect, t: number): Rect {
  const ca = { x: a.x + a.w / 2, y: a.y + a.h / 2 };
  const cb = { x: b.x + b.w / 2, y: b.y + b.h / 2 };
  const w = Math.exp(Math.log(a.w) + (Math.log(b.w) - Math.log(a.w)) * t); // zoom feels linear in log space
  const h = Math.exp(Math.log(a.h) + (Math.log(b.h) - Math.log(a.h)) * t);
  const cx = ca.x + (cb.x - ca.x) * t;
  const cy = ca.y + (cb.y - ca.y) * t;
  return { x: cx - w / 2, y: cy - h / 2, w, h };
}

export const sameRect = (a: Rect, b: Rect) =>
  Math.abs(a.x - b.x) + Math.abs(a.y - b.y) + Math.abs(a.w - b.w) + Math.abs(a.h - b.h) < 4;

// Source-pixel scale and offset that put `r` in the middle of a pw x ph panel.
// Never above 1:1 source pixels, so zooms stay sharp.
export function fit(r: Rect, pw: number, ph: number, cropX = 1) {
  const contain = Math.min(pw / SOURCE.w, ph / SOURCE.h);
  const s = Math.max(contain, Math.min((pw * cropX) / r.w, ph / r.h, 1));
  const clamp = (t: number, size: number, panel: number) =>
    size * s >= panel ? Math.min(0, Math.max(panel - size * s, t)) : (panel - size * s) / 2;
  const tx = clamp(pw / 2 - (r.x + r.w / 2) * s, SOURCE.w, pw);
  const ty = clamp(ph / 2 - (r.y + r.h / 2) * s, SOURCE.h, ph);
  return { s, tx, ty };
}
