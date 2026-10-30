import { Audio } from "@remotion/media";
import { AbsoluteFill, interpolate, Sequence, spring, staticFile, useCurrentFrame } from "remotion";
import { theme } from "./config";
import { Footage, shotAt } from "./Footage";
import { Chip, inter, Outro, Pill, Title } from "./Overlays";
import { FPS, hasMusic, OUTRO, plan, TITLE } from "./plan";

// Music sits under the voice and dips while a command is spoken.
function musicVolume(frame: number) {
  const shot = shotAt(frame);
  const speaking = shot && frame < shot.action.from + 6;
  const fadeOut = interpolate(frame, [plan.total - 60, plan.total], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (speaking ? 0.16 : 0.32) * fadeOut;
}

const Overlays: React.FC<{ pillSize: number; chipSize: number; pillBottom: number; chipTop: number }> = ({
  pillSize,
  chipSize,
  pillBottom,
  chipTop,
}) => {
  const frame = useCurrentFrame();
  const shot = shotAt(frame);
  return (
    <>
      {shot && (
        <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: pillBottom }}>
          <Pill key={shot.from} shot={shot} size={pillSize} />
        </AbsoluteFill>
      )}
      {plan.shots
        .filter((s) => s.section)
        .map((s) => (
          <div key={s.n} style={{ position: "absolute", top: chipTop, left: chipSize * 2.6 }}>
            <Chip text={s.section!} from={s.from} size={chipSize} />
          </div>
        ))}
    </>
  );
};

export const Wide: React.FC = () => (
  <AbsoluteFill style={{ background: theme.bg }}>
    <Footage shots={plan.shots} width={1920} height={1080} />
    <AbsoluteFill style={{ background: "linear-gradient(to top, rgba(0,0,0,0.45), transparent 22%)" }} />
    <Overlays pillSize={38} chipSize={28} pillBottom={56} chipTop={52} />
    <Sequence from={plan.titleFrom} durationInFrames={TITLE}>
      <Title size={128} />
    </Sequence>
    <Sequence from={plan.outroFrom} durationInFrames={OUTRO}>
      <Outro size={46} />
    </Sequence>
    {hasMusic && <Audio src={staticFile("music.mp3")} volume={musicVolume} />}
  </AbsoluteFill>
);

// 9:16: the footage in a panel shaped like a window, a headline above, the pill below.
const PANEL = { top: 520, h: 860 };

const Headline: React.FC = () => {
  const frame = useCurrentFrame();
  const p = spring({ frame: frame - plan.titleFrom, fps: FPS, config: { damping: 16 } });
  return (
    <div
      style={{
        position: "absolute",
        top: 300,
        width: "100%",
        textAlign: "center",
        fontFamily: inter,
        fontWeight: 800,
        fontSize: 76,
        letterSpacing: -2,
        color: theme.text,
        opacity: p,
      }}
    >
      Just <span style={{ color: theme.accent }}>say</span> it.
    </div>
  );
};

export const Vertical: React.FC = () => (
  <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 40%, #171c27 0%, ${theme.bg} 70%)` }}>
    <Headline />
    <div style={{ position: "absolute", top: PANEL.top, left: 0, width: 1080, height: PANEL.h, overflow: "hidden" }}>
      <Footage shots={plan.shots} width={1080} height={PANEL.h} cropX={1.3} />
    </div>
    <Overlays pillSize={44} chipSize={26} pillBottom={330} chipTop={PANEL.top + 28} />
    <Sequence from={plan.titleFrom} durationInFrames={TITLE}>
      <Title size={118} />
    </Sequence>
    <Sequence from={plan.outroFrom} durationInFrames={OUTRO}>
      <Outro size={38} />
    </Sequence>
    {hasMusic && <Audio src={staticFile("music.mp3")} volume={musicVolume} />}
  </AbsoluteFill>
);
