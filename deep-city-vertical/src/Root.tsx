import React from "react";
import { Composition } from "remotion";
import { DeepCity, DURATION, FPS } from "./DeepCity";
import { H, W } from "./rig";

export const RemotionRoot: React.FC = () => (
  <Composition id="DeepCity" component={DeepCity} durationInFrames={DURATION} fps={FPS} width={W} height={H} />
);
