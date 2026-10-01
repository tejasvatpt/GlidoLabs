import { Composition } from "remotion";
import { CaptionedVideo } from "./CaptionedVideo";
import type { CaptionProps } from "./types";
import sample from "../sample-props.json";

export const Root = () => (
  <Composition
    id="CaptionedVideo"
    component={CaptionedVideo}
    defaultProps={sample as CaptionProps}
    calculateMetadata={({ props }) => {
      const { fps, width, height, duration } = props.captions.video;
      return { fps, width, height, durationInFrames: Math.ceil(duration * fps) };
    }}
  />
);
