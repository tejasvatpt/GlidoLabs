export type Role = "normal" | "emphasis" | "hook";

export type CaptionWord = { text: string; start: number; end: number; role: Role; emphasis: number };

export type CaptionGroup = {
  id: number;
  layer: "normal" | "hook";
  start: number;
  end: number;
  lines: number[][];
  words: CaptionWord[];
};

export type Captions = {
  version: number;
  style: string;
  source: string;
  video: { width: number; height: number; fps: number; duration: number };
  groups: CaptionGroup[];
};

type Font = { family: string; file: string; weight: number };

export type Style = {
  name: string;
  fonts: { caption: Font; emphasis: Font; hook: Font };
  caption: {
    fontSize: number; lineHeight: number; letterSpacing: number; wordGap: number;
    baselineY: number; maxWidth: number; color: string; activeColor: string; activeBackground: string;
    shadow: string; emphasis: { uppercase: boolean; scale: number; color: string };
  };
  hook: {
    fontSize: number; maxWidth: number; uppercase: boolean; topY: number; color: string; accentColor: string;
    shadow: string; box: { color: string; settledColor: string; radius: number; paddingX: number; paddingY: number };
  };
  animation: {
    groupInMs: number; groupInDistance: number; wordPopScale: number; wordPopMs: number; colorFadeMs: number;
    hookInMs: number; hookInScale: number; hookSettleMs: number; hookOutMs: number;
  };
};

export type CaptionProps = { videoSrc: string; captions: Captions; style: Style };
