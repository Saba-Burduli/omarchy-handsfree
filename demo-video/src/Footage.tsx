import { Video } from "@remotion/media";
import { Easing, interpolate, Sequence, spring, staticFile, useCurrentFrame } from "remotion";
import { fit, FPS, lerpRect, plan, Rect, sameRect, Shot, SOURCE } from "./plan";

const src = staticFile("take/screen.mp4");
const EASE_OUT = 24; // frames to ease toward the next shot's framing

// Camera for one shot at a given frame: the spoken command plays framed on
// what was on screen, then springs onto the window the command log reported.
function cameraAt(shot: Shot, next: Shot | undefined, frame: number): Rect {
  let r = shot.before;
  if (frame >= shot.action.from) {
    const p = spring({ frame: frame - shot.action.from, fps: FPS, config: { damping: 200, mass: 0.7 }, durationInFrames: 40 });
    r = lerpRect(shot.before, shot.rect, p);
  }
  const into = next && next.from === shot.end ? next.before : null;
  if (into && !sameRect(into, shot.rect) && frame >= shot.end - EASE_OUT) {
    const p = interpolate(frame, [shot.end - EASE_OUT, shot.end], [0, 1], { easing: Easing.inOut(Easing.cubic) });
    r = lerpRect(r, into, p);
  }
  return r;
}

export const Footage: React.FC<{ shots: Shot[]; width: number; height: number; cropX?: number }> = ({
  shots,
  width,
  height,
  cropX = 1,
}) => {
  const frame = useCurrentFrame();
  const i = shots.findIndex((s) => frame >= s.from && frame < s.end);
  const shot = shots[i] ?? shots[shots.length - 1];
  const { s, tx, ty } = fit(cameraAt(shot, shots[i + 1], frame), width, height, cropX);
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          width: SOURCE.w,
          height: SOURCE.h,
          transformOrigin: "0 0",
          transform: `translate(${tx}px, ${ty}px) scale(${s})`,
        }}
      >
        {shots.flatMap((shot) =>
          [shot.speech, shot.action].map((seg, k) => (
            <Sequence key={`${shot.n}-${shot.from}-${k}`} from={seg.from} durationInFrames={seg.dur} premountFor={30}>
              <Video src={src} trimBefore={Math.round(seg.src * FPS)} volume={seg.muted ? 0 : 1} style={{ width: SOURCE.w, height: SOURCE.h }} />
            </Sequence>
          )),
        )}
      </div>
    </div>
  );
};

export const shotAt = (frame: number) => plan.shots.find((s) => frame >= s.from && frame < s.end);
