import { Audio } from "@remotion/media";
import { AbsoluteFill, interpolate, Sequence, spring, staticFile, useCurrentFrame } from "remotion";
import { theme } from "./config";
import { Footage, shotAt } from "./Footage";
import { Chip, inter, Intro, Outro, Pill } from "./Overlays";
import { FPS, hasMusic, OUTRO, plan, speaking } from "./plan";

// Music sits under the voices and dips whenever someone is talking.
function musicVolume(frame: number) {
  const fade = interpolate(frame, [0, 20, plan.total - 90, plan.total], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (speaking(frame) ? 0.07 : 0.2) * fade;
}

// Narrator lines and sound effects, placed by the plan.
const Sound: React.FC = () => (
  <>
    {hasMusic && <Audio src={staticFile("music.mp3")} volume={musicVolume} />}
    {[...plan.voice, ...plan.sfx].map((cue, i) => (
      <Sequence key={i} from={cue.from} layout="none">
        <Audio src={staticFile(cue.src)} volume={cue.volume} />
      </Sequence>
    ))}
  </>
);

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
      {plan.chips.map((c) => (
        <div key={c.from} style={{ position: "absolute", top: chipTop, left: chipSize * 2.6 }}>
          <Chip text={c.text} from={c.from} size={chipSize} />
        </div>
      ))}
    </>
  );
};

const Cards: React.FC<{ introSize: number; outroSize: number }> = ({ introSize, outroSize }) => (
  <>
    <Sequence from={plan.introFrom} durationInFrames={plan.introDur}>
      <Intro size={introSize} voAt={plan.voice[0].from - plan.introFrom} duration={plan.introDur} />
    </Sequence>
    <Sequence from={plan.outroFrom} durationInFrames={OUTRO}>
      <Outro size={outroSize} />
    </Sequence>
  </>
);

export const Wide: React.FC = () => (
  <AbsoluteFill style={{ background: theme.bg }}>
    <Footage shots={plan.shots} width={1920} height={1080} />
    <AbsoluteFill style={{ background: "linear-gradient(to top, rgba(0,0,0,0.45), transparent 22%)" }} />
    <Overlays pillSize={40} chipSize={28} pillBottom={56} chipTop={52} />
    <Cards introSize={60} outroSize={46} />
    <Sound />
  </AbsoluteFill>
);

// 9:16: the footage in a panel shaped like a window, a headline above, the pill below.
const PANEL = { top: 520, h: 860 };

const Headline: React.FC = () => {
  const frame = useCurrentFrame();
  const p = spring({ frame: frame - (plan.introFrom + plan.introDur), fps: FPS, config: { damping: 16 } });
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
    <Cards introSize={46} outroSize={38} />
    <Sound />
  </AbsoluteFill>
);
