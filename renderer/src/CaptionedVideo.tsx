import { useEffect, useState } from "react";
import { AbsoluteFill, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { fitText } from "@remotion/layout-utils";
import { Video } from "@remotion/media";
import type { CaptionGroup, CaptionProps, CaptionWord, Style } from "./types";

// Eclipse animates with hard cuts: groups, highlights and the hook settle all switch on a single frame.
const useTime = () => {
  const { fps, width, height } = useVideoConfig();
  return { t: useCurrentFrame() / fps, width, height };
};

const activeGroup = (groups: CaptionGroup[], layer: CaptionGroup["layer"], t: number) =>
  groups.find((g) => g.layer === layer && g.start <= t && t < g.end);

const useFonts = (style: Style) => {
  const [handle] = useState(() => delayRender("Loading fonts"));
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const unique = [...new Map(Object.values(style.fonts).map((f) => [f.family + f.file, f])).values()];
    Promise.all(unique.map((f) =>
      new FontFace(f.family, `url(${staticFile(`${style.name}/${f.file}`)})`, { weight: String(f.weight) })
        .load().then((face) => document.fonts.add(face)),
    )).then(() => [setLoaded(true), continueRender(handle)], cancelRender);
  }, [handle, style]);
  return loaded;
};

const Word = ({ word, active, style }: { word: CaptionWord; active: boolean; style: Style }) => {
  const { caption: c, fonts } = style;
  const emphasized = word.role !== "normal";
  return (
    <span style={{
      display: "inline-block", margin: `0 ${c.wordGap / 2}em`, padding: "0 0.14em", borderRadius: "0.2em",
      background: active ? c.activeBackground : "transparent",
      color: active ? c.activeColor : emphasized ? c.emphasis.color : c.color,
      ...(emphasized && {
        fontFamily: fonts.emphasis.family, fontWeight: fonts.emphasis.weight, fontSize: `${c.emphasis.scale}em`,
        textTransform: c.emphasis.uppercase ? "uppercase" : "none",
      }),
    }}>
      {word.text}
    </span>
  );
};

const CaptionLayer = ({ captions, style }: CaptionProps) => {
  const { t, width, height } = useTime();
  const group = activeGroup(captions.groups, "normal", t);
  if (!group) return null;
  const c = style.caption;
  const active = group.words.findIndex((w) => w.start <= t && t < w.end);
  return (
    <div style={{
      position: "absolute", left: "50%", top: c.baselineY * height, width: c.maxWidth * width,
      transform: "translate(-50%, -100%)", textAlign: "center", color: c.color, textShadow: c.shadow,
      fontFamily: style.fonts.caption.family, fontWeight: style.fonts.caption.weight,
      fontSize: c.fontSize * width, lineHeight: c.lineHeight,
    }}>
      {group.lines.map((line, i) => (
        <div key={i}>{line.map((w) => <Word key={w} word={group.words[w]} active={w === active} style={style} />)}</div>
      ))}
    </div>
  );
};

const HookLayer = ({ captions, style }: CaptionProps) => {
  const { t, width, height } = useTime();
  const group = activeGroup(captions.groups, "hook", t);
  if (!group) return null;
  const { hook: h, fonts } = style;
  const text = group.words.map((w) => w.text).join(" ").toUpperCase();
  const fitted = fitText({ text, withinWidth: h.maxWidth * width, fontFamily: fonts.hook.family, fontWeight: fonts.hook.weight });
  const settled = t - group.start >= h.settleMs / 1000;
  return (
    <div style={{ position: "absolute", top: h.topY * height, width: "100%", display: "flex", justifyContent: "center" }}>
      <div style={{
        background: settled ? "transparent" : h.box.color, borderRadius: h.box.radius * width,
        padding: `${h.box.paddingY * width}px ${h.box.paddingX * width}px`,
        color: settled ? h.color : h.accentColor, textShadow: settled ? h.shadow : "none",
        fontFamily: fonts.hook.family, fontWeight: fonts.hook.weight,
        fontSize: Math.min(h.fontSize * width, fitted.fontSize), lineHeight: 1.05, whiteSpace: "nowrap",
      }}>
        {text}
      </div>
    </div>
  );
};

export const CaptionedVideo = (props: CaptionProps) => {
  const fontsLoaded = useFonts(props.style);
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Video src={props.videoSrc} />
      {fontsLoaded && <CaptionLayer {...props} />}
      {fontsLoaded && <HookLayer {...props} />}
    </AbsoluteFill>
  );
};
