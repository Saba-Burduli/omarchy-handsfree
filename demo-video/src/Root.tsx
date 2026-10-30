import { Composition } from "remotion";
import { Vertical, Wide } from "./Demo";
import { FPS, plan } from "./plan";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Wide" component={Wide} durationInFrames={plan.total} fps={FPS} width={1920} height={1080} />
    <Composition id="Vertical" component={Vertical} durationInFrames={plan.total} fps={FPS} width={1080} height={1920} />
  </>
);
