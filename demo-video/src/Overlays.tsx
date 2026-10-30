import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import { measureText } from "@remotion/layout-utils";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { config, theme } from "./config";
import { envelope, envelopeFps, FPS, Shot } from "./plan";

export const inter = loadInter("normal", {
  weights: ["500", "600", "800"],
  subsets: ["latin"],
}).fontFamily;
export const mono = loadMono("normal", {
  weights: ["500", "700"],
  subsets: ["latin"],
}).fontFamily;

const BARS = 22;

// -- listening pill: a live waveform while the command is spoken, then it
// morphs into the words handsfree recognized ---------------------------------
export const Pill: React.FC<{ shot: Shot; size: number }> = ({
  shot,
  size,
}) => {
  const frame = useCurrentFrame();
  const enter = spring({
    frame: frame - shot.from,
    fps: FPS,
    config: { damping: 14, stiffness: 220 },
  });
  const exit = interpolate(frame, [shot.end - 7, shot.end], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const morph = spring({
    frame: frame - shot.action.from,
    fps: FPS,
    config: { damping: 18, stiffness: 180 },
  });

  const h = size * 1.9;
  const fontSize = size;
  const textW = measureText({
    text: shot.heard,
    fontFamily: inter,
    fontWeight: "600",
    fontSize,
  }).width;
  const waveW = BARS * size * 0.24;
  const inner = interpolate(morph, [0, 1], [waveW, textW + size * 0.9]);
  const icon = h - size * 0.5;

  // Voice level at the matching moment of the source recording.
  const srcTime = shot.speech.src + (frame - shot.speech.from) / FPS;
  const level = (back: number) =>
    envelope[Math.max(0, Math.round((srcTime - back) * envelopeFps))] ?? 0;

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
        <svg
          width={icon * 0.5}
          height={icon * 0.5}
          viewBox="0 0 24 24"
          fill="none"
          stroke="#0d0f12"
          strokeWidth={2.6}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
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
      <div
        style={{
          position: "relative",
          width: inner,
          height: h,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            opacity: 1 - morph,
          }}
        >
          {Array.from({ length: BARS }, (_, i) => {
            const bell = Math.exp(
              -(((i - (BARS - 1) / 2) / (BARS / 3.2)) ** 2),
            );
            const v = Math.min(
              1,
              level(Math.abs(i - (BARS - 1) / 2) * 0.012) * 1.6,
            );
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
export const Chip: React.FC<{ text: string; from: number; size: number }> = ({
  text,
  from,
  size,
}) => {
  const frame = useCurrentFrame();
  const inP = spring({
    frame: frame - from,
    fps: FPS,
    config: { damping: 16, stiffness: 200 },
  });
  const out = interpolate(frame, [from + 100, from + 112], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
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
      <div
        style={{
          width: size * 0.55,
          height: size * 0.55,
          borderRadius: size,
          background: theme.accent,
        }}
      />
      {text}
    </div>
  );
};

// -- intro: what the project is, timed to the narrator ---------------------------
const MicMark: React.FC<{ size: number }> = ({ size }) => (
  <div
    style={{
      width: size,
      height: size,
      borderRadius: size,
      display: "grid",
      placeItems: "center",
      background: theme.accent,
      boxShadow: `0 0 ${size * 0.6}px ${theme.accent}66`,
    }}
  >
    <svg
      width={size * 0.5}
      height={size * 0.5}
      viewBox="0 0 24 24"
      fill="none"
      stroke="#0d0f12"
      strokeWidth={2.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  </div>
);

export const Intro: React.FC<{
  size: number;
  voAt: number;
  duration: number;
}> = ({ size, voAt, duration }) => {
  const frame = useCurrentFrame();
  const { height } = useVideoConfig();
  const ts = (frame - voAt) / FPS; // seconds into the narration
  const sp = (at: number, damping = 15) =>
    spring({
      frame: frame - voAt - at * FPS,
      fps: FPS,
      config: { damping, stiffness: 170 },
    });
  const window = (from: number, to: number) =>
    interpolate(ts, [from - 0.01, from, to - 0.15, to], [0, 1, 1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  const fadeIn = interpolate(frame, [0, 12], [0, 1], {
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(frame, [duration - 12, duration], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const { line, chips, offline } = config.intro;

  // The name starts big in the middle, then becomes a header for the rest.
  const dock = sp(line[0].at - 0.1, 20);
  const name = sp(config.intro.name);
  const glow = 0.5 + 0.5 * Math.sin(frame / 25);

  return (
    <AbsoluteFill
      style={{
        opacity: fadeIn * fadeOut,
        transform: `scale(${interpolate(fadeOut, [0, 1], [1.06, 1])})`,
        background: `radial-gradient(circle at ${50 + 8 * Math.sin(frame / 90)}% ${38 + 6 * Math.cos(frame / 70)}%, #1d2640 0%, ${theme.bg} 60%)`,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          position: "absolute",
          display: "flex",
          alignItems: "center",
          gap: size * 0.5,
          top: "50%",
          transform: `translateY(-50%) translateY(${-dock * height * 0.3}px) scale(${interpolate(name, [0, 1], [0.7, 1]) * interpolate(dock, [0, 1], [1, 0.55])})`,
          opacity: name,
        }}
      >
        <MicMark size={size * 2.2} />
        <div
          style={{
            fontFamily: inter,
            fontWeight: 800,
            fontSize: size * 2.1,
            letterSpacing: -size * 0.06,
            color: theme.text,
            whiteSpace: "nowrap",
          }}
        >
          {config.name}
        </div>
      </div>

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div
          style={{
            width: "86%",
            textAlign: "center",
            opacity: window(line[0].at, chips[0].at),
            fontFamily: inter,
            fontWeight: 800,
            fontSize: size * 1.75,
            lineHeight: 1.15,
            letterSpacing: -size * 0.04,
          }}
        >
          {line.map(({ at, text: w }, i) => {
            const p = sp(at);
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  marginRight: size * 0.45,
                  opacity: p,
                  transform: `translateY(${(1 - p) * size * 0.6}px)`,
                  color: /voice/i.test(w) ? theme.accent : theme.text,
                }}
              >
                {w}
              </span>
            );
          })}
        </div>
      </AbsoluteFill>

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div
          style={{
            width: "90%",
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: size * 0.5,
            opacity: window(chips[0].at, offline),
          }}
        >
          {chips.map((c, i) => {
            const p = sp(c.at, 12);
            const last = i === chips.length - 1;
            return (
              <div
                key={c.text}
                style={{
                  padding: `${size * 0.45}px ${size * 0.9}px`,
                  borderRadius: size * 2,
                  fontFamily: inter,
                  fontWeight: 700,
                  fontSize: size * 1.05,
                  color: last ? "#0d0f12" : theme.text,
                  background: last ? theme.accent : theme.panel,
                  border: `2px solid ${last ? theme.accent : "rgba(255,255,255,0.14)"}`,
                  opacity: p,
                  transform: `scale(${interpolate(p, [0, 1], [0.5, 1])})`,
                }}
              >
                {c.text}
              </div>
            );
          })}
        </div>
      </AbsoluteFill>

      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: size * 0.4,
            opacity: window(offline, 99),
          }}
        >
          <div
            style={{
              transform: `scale(${sp(offline, 11)})`,
              width: size * 2.4,
              height: size * 2.4,
              borderRadius: size * 0.6,
              display: "grid",
              placeItems: "center",
              background: theme.panel,
              border: `2px solid ${theme.ok}`,
              boxShadow: `0 0 ${size * glow}px ${theme.ok}55`,
            }}
          >
            <svg
              width={size * 1.2}
              height={size * 1.2}
              viewBox="0 0 24 24"
              fill="none"
              stroke={theme.ok}
              strokeWidth={2.2}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="5" y="11" width="14" height="10" rx="2" />
              <path d="M8 11V7a4 4 0 0 1 8 0v4" />
            </svg>
          </div>
          <div
            style={{
              fontFamily: inter,
              fontWeight: 800,
              fontSize: size * 1.75,
              color: theme.text,
              letterSpacing: -size * 0.04,
              opacity: sp(offline + 0.15),
              textAlign: "center",
            }}
          >
            Runs 100% offline.
          </div>
          <div
            style={{
              fontFamily: inter,
              fontWeight: 500,
              fontSize: size * 0.85,
              color: theme.dim,
              opacity: sp(offline + 0.45),
              textAlign: "center",
            }}
          >
            Nothing leaves your machine.
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

// -- outro ------------------------------------------------------------------------
export const Outro: React.FC<{ size: number }> = ({ size }) => {
  const frame = useCurrentFrame();
  const sp = (delay: number) =>
    spring({
      frame: frame - delay,
      fps: FPS,
      config: { damping: 16, stiffness: 170 },
    });
  const rise = (delay: number) => ({
    opacity: sp(delay),
    transform: `translateY(${(1 - sp(delay)) * size * 0.5}px)`,
  });
  const typed = (line: string, start: number) =>
    line.slice(0, Math.max(0, Math.floor((frame - start) * 1.6)));
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
      <div
        style={{
          fontFamily: inter,
          fontWeight: 800,
          fontSize: size * 2.2,
          letterSpacing: -size * 0.07,
          whiteSpace: "nowrap",
          color: theme.text,
          ...rise(4),
        }}
      >
        {config.name}
      </div>
      <div
        style={{
          fontFamily: inter,
          fontWeight: 500,
          fontSize: size * 0.85,
          color: theme.dim,
          marginTop: -size * 0.4,
          ...rise(10),
        }}
      >
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
          <div
            key={i}
            style={{
              whiteSpace: "pre-wrap",
              wordBreak: "break-all",
              lineHeight: 1.5,
            }}
          >
            <span style={{ color: theme.ok }}>$ </span>
            {typed(line, 30 + i * 36)}
          </div>
        ))}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: size * 0.35,
          fontFamily: inter,
          fontWeight: 600,
          fontSize: size * 0.75,
          color: theme.text,
          ...rise(config.outro.keys * FPS),
        }}
      >
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
      <div
        style={{
          fontFamily: inter,
          fontWeight: 600,
          fontSize: size * 0.8,
          color: theme.accent,
          ...rise(config.outro.repo * FPS),
        }}
      >
        {config.repo}
      </div>
      <div
        style={{
          fontFamily: inter,
          fontWeight: 500,
          fontSize: size * 0.42,
          color: theme.dim,
          ...rise(config.outro.footer * FPS),
        }}
      >
        Every action in this video was triggered by voice.
      </div>
    </AbsoluteFill>
  );
};
