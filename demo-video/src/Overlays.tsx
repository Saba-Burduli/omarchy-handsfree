import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import { measureText } from "@remotion/layout-utils";
import { AbsoluteFill, interpolate, spring, useCurrentFrame } from "remotion";
import { config, theme } from "./config";
import { envelope, envelopeFps, FPS, Shot } from "./plan";

export const inter = loadInter("normal", { weights: ["500", "600", "800"], subsets: ["latin"] }).fontFamily;
export const mono = loadMono("normal", { weights: ["500", "700"], subsets: ["latin"] }).fontFamily;

const BARS = 22;

// -- listening pill: a live waveform while the command is spoken, then it
// morphs into the words handsfree recognized ---------------------------------
export const Pill: React.FC<{ shot: Shot; size: number }> = ({ shot, size }) => {
  const frame = useCurrentFrame();
  const enter = spring({ frame: frame - shot.from, fps: FPS, config: { damping: 14, stiffness: 220 } });
  const exit = interpolate(frame, [shot.end - 7, shot.end], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const morph = spring({ frame: frame - shot.action.from, fps: FPS, config: { damping: 18, stiffness: 180 } });

  const h = size * 1.9;
  const fontSize = size;
  const textW = measureText({ text: shot.heard, fontFamily: inter, fontWeight: "600", fontSize }).width;
  const waveW = BARS * size * 0.24;
  const inner = interpolate(morph, [0, 1], [waveW, textW + size * 0.9]);
  const icon = h - size * 0.5;

  // Voice level at the matching moment of the source recording.
  const srcTime = shot.speech.src + (frame - shot.speech.from) / FPS;
  const level = (back: number) => envelope[Math.max(0, Math.round((srcTime - back) * envelopeFps))] ?? 0;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: size * 0.45,
        height: h,
        padding: `0 ${size * 0.75}px 0 ${size * 0.25}px`,
        borderRadius: h,
        background: "rgba(16,18,23,0.86)",
        border: "1.5px solid rgba(255,255,255,0.13)",
        boxShadow: "0 18px 50px rgba(0,0,0,0.55)",
        backdropFilter: "blur(18px)",
        transform: `scale(${interpolate(enter, [0, 1], [0.6, 1]) * interpolate(exit, [0, 1], [0.9, 1])})`,
        opacity: enter * exit,
      }}
    >
      <div
        style={{
          width: icon,
          height: icon,
          borderRadius: icon,
          display: "grid",
          placeItems: "center",
          background: morph > 0.5 ? theme.ok : theme.accent,
          boxShadow: `0 0 ${(1 - morph) * level(0) * size * 1.6}px ${theme.accent}`,
        }}
      >
        <svg width={icon * 0.5} height={icon * 0.5} viewBox="0 0 24 24" fill="none" stroke="#0d0f12" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round">
          {morph > 0.5 ? (
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          ) : (
            <>
              <rect x="9" y="3" width="6" height="11" rx="3" />
              <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
            </>
          )}
        </svg>
      </div>
      <div style={{ position: "relative", width: inner, height: h, overflow: "hidden" }}>
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "space-between", opacity: 1 - morph }}>
          {Array.from({ length: BARS }, (_, i) => {
            const bell = Math.exp(-(((i - (BARS - 1) / 2) / (BARS / 3.2)) ** 2));
            const v = Math.min(1, level(Math.abs(i - (BARS - 1) / 2) * 0.012) * 1.6);
            return (
              <div
                key={i}
                style={{
                  width: size * 0.12,
                  height: Math.max(size * 0.14, v * bell * h * 0.62),
                  borderRadius: size,
                  background: theme.text,
                  opacity: 0.55 + v * 0.45,
                }}
              />
            );
          })}
        </div>
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            whiteSpace: "nowrap",
            fontFamily: inter,
            fontWeight: 600,
            fontSize,
            color: theme.text,
            opacity: morph,
            transform: `translateY(${(1 - morph) * size * 0.5}px)`,
          }}
        >
          {shot.heard}
        </div>
      </div>
    </div>
  );
};

// -- small section chip -------------------------------------------------------
export const Chip: React.FC<{ text: string; from: number; size: number }> = ({ text, from, size }) => {
  const frame = useCurrentFrame();
  const inP = spring({ frame: frame - from, fps: FPS, config: { damping: 16, stiffness: 200 } });
  const out = interpolate(frame, [from + 100, from + 112], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: size * 0.5,
        padding: `${size * 0.45}px ${size * 0.9}px`,
        borderRadius: size * 2,
        background: "rgba(16,18,23,0.86)",
        border: "1.5px solid rgba(255,255,255,0.13)",
        fontFamily: inter,
        fontWeight: 600,
        fontSize: size,
        letterSpacing: size * 0.08,
        textTransform: "uppercase",
        color: theme.text,
        opacity: inP * out,
        transform: `translateX(${(1 - inP) * -size * 3}px)`,
      }}
    >
      <div style={{ width: size * 0.55, height: size * 0.55, borderRadius: size, background: theme.accent }} />
      {text}
    </div>
  );
};

// -- title right after the hook ------------------------------------------------
export const Title: React.FC<{ size: number }> = ({ size }) => {
  const frame = useCurrentFrame();
  const bg = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: `rgba(13,15,18,${0.96 * bg})`, justifyContent: "center", alignItems: "center" }}>
      <div style={{ fontFamily: inter, fontWeight: 800, fontSize: size, lineHeight: 1.08, letterSpacing: -size * 0.03, textAlign: "center" }}>
        {config.title.map((line, li) => (
          <div key={li} style={{ display: "flex", justifyContent: "center", gap: size * 0.26 }}>
            {line.split(" ").map((word, wi) => {
              const p = spring({ frame: frame - 3 - (li * 3 + wi) * 3, fps: FPS, config: { damping: 15, stiffness: 190 } });
              const accent = /voice/i.test(word);
              return (
                <span
                  key={wi}
                  style={{
                    color: accent ? theme.accent : theme.text,
                    opacity: p,
                    transform: `translateY(${(1 - p) * size * 0.45}px) scale(${0.9 + p * 0.1})`,
                    display: "inline-block",
                  }}
                >
                  {word}
                </span>
              );
            })}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

// -- outro ------------------------------------------------------------------------
export const Outro: React.FC<{ size: number }> = ({ size }) => {
  const frame = useCurrentFrame();
  const sp = (delay: number) => spring({ frame: frame - delay, fps: FPS, config: { damping: 16, stiffness: 170 } });
  const rise = (delay: number) => ({ opacity: sp(delay), transform: `translateY(${(1 - sp(delay)) * size * 0.5}px)` });
  const typed = (line: string, start: number) => line.slice(0, Math.max(0, Math.floor((frame - start) * 1.6)));
  const bg = interpolate(frame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 30%, #1a2030 0%, ${theme.bg} 65%)`,
        opacity: bg,
        justifyContent: "center",
        alignItems: "center",
        gap: size * 0.9,
        padding: size * 1.5,
        textAlign: "center",
      }}
    >
      <div style={{ fontFamily: inter, fontWeight: 800, fontSize: size * 2.2, letterSpacing: -size * 0.07, whiteSpace: "nowrap", color: theme.text, ...rise(4) }}>
        {config.name}
      </div>
      <div style={{ fontFamily: inter, fontWeight: 500, fontSize: size * 0.85, color: theme.dim, marginTop: -size * 0.4, ...rise(10) }}>
        {config.tagline}
      </div>
      <div
        style={{
          fontFamily: mono,
          fontWeight: 500,
          fontSize: size * 0.62,
          color: theme.text,
          background: theme.panel,
          border: "1.5px solid rgba(255,255,255,0.1)",
          borderRadius: size * 0.5,
          padding: `${size * 0.6}px ${size * 0.9}px`,
          textAlign: "left",
          minWidth: size * 20,
          maxWidth: "100%",
          ...rise(16),
        }}
      >
        {config.install.map((line, i) => (
          <div key={i} style={{ whiteSpace: "pre-wrap", wordBreak: "break-all", lineHeight: 1.5 }}>
            <span style={{ color: theme.ok }}>$ </span>
            {typed(line, 22 + i * 40)}
          </div>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: size * 0.35, fontFamily: inter, fontWeight: 600, fontSize: size * 0.75, color: theme.text, ...rise(105) }}>
        then
        {config.keys.map((k, i) => (
          <span key={k} style={{ display: "contents" }}>
            {i > 0 && <span style={{ color: theme.dim }}>+</span>}
            <span
              style={{
                fontFamily: mono,
                fontWeight: 700,
                padding: `${size * 0.12}px ${size * 0.4}px`,
                borderRadius: size * 0.25,
                background: theme.panel,
                border: "1.5px solid rgba(255,255,255,0.18)",
                borderBottomWidth: 4,
              }}
            >
              {k}
            </span>
          </span>
        ))}
        and talk.
      </div>
      <div style={{ fontFamily: inter, fontWeight: 600, fontSize: size * 0.8, color: theme.accent, ...rise(125) }}>{config.repo}</div>
      <div style={{ fontFamily: inter, fontWeight: 500, fontSize: size * 0.42, color: theme.dim, ...rise(140) }}>
        Every action in this video was triggered by voice.
      </div>
    </AbsoluteFill>
  );
};
