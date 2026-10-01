import { Composition } from "remotion";
import { CaptionedVideo } from "./CaptionedVideo";
import type { CaptionProps } from "./types";
import style from "../../styles/eclipse/style.json";

// Real props come from the backend (render.mjs / Player); these defaults only let the composition open in the studio.
const defaults: CaptionProps = {
  videoSrc: "",
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
      return { fps, width, height, durationInFrames: Math.ceil(duration * fps) };
    }}
  />
);
