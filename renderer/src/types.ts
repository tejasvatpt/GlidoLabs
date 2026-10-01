export type CaptionWord = { text: string; start: number; end: number; role: "normal" | "emphasis" | "hook"; emphasis: number };

export type CaptionGroup = { id: number; layer: "normal" | "hook"; start: number; end: number; lines: number[][]; words: CaptionWord[] };

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
    fontSize: number; lineHeight: number; wordGap: number; baselineY: number; maxWidth: number;
    color: string; activeColor: string; activeBackground: string; shadow: string;
    emphasis: { uppercase: boolean; scale: number; color: string };
  };
  hook: {
    fontSize: number; maxWidth: number; topY: number; settleMs: number; color: string; accentColor: string; shadow: string;
    box: { color: string; radius: number; paddingX: number; paddingY: number };
  };
};

export type CaptionProps = { videoSrc: string; captions: Captions; style: Style };
