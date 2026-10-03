import { Composition } from "remotion";
import { CaptionedVideo } from "./CaptionedVideo";
import type { CaptionProps } from "./types";
import style from "../../styles/eclipse/style.json";

// Real props come from the backend (render.mjs); these defaults only let the composition open in the studio.
const defaults: CaptionProps = {
  style: style as CaptionProps["style"],
  captions: { version: 1, style: "eclipse", source: "", video: { width: 1080, height: 1920, fps: 30, duration: 1 }, groups: [] },
};

export const Root = () => (
  <Composition
    id="CaptionedVideo"
    component={CaptionedVideo}
    defaultProps={defaults}
    calculateMetadata={({ props }) => {
      const { fps, width, height, duration } = props.captions.video;
      return { fps, width: width * 2, height, durationInFrames: props.frames?.length ?? Math.ceil(duration * fps) };
    }}
  />
);
