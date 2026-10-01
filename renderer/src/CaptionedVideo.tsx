import { useEffect, useState } from "react";
import {
  AbsoluteFill, cancelRender, continueRender, delayRender, interpolate, interpolateColors,
  spring, staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { fitText } from "@remotion/layout-utils";
import { Video } from "@remotion/media";
import type { CaptionGroup, CaptionProps, CaptionWord, Style } from "./types";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const useTime = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  return { frame, fps, width, height, t: frame / fps, frames: (ms: number) => (ms / 1000) * fps };
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
  const { frame, fps, frames } = useTime();
  const { caption: c, animation: a } = style;
  const since = frame - word.start * fps;
  const emphasized = word.role !== "normal";
  const pop = active ? Math.sin(Math.PI * interpolate(since, [0, frames(a.wordPopMs)], [0, 1], clamp)) : 0;
  const rest = emphasized ? c.emphasis.color : c.color;
  return (
    <span style={{
      display: "inline-block",
      margin: `0 ${c.wordGap / 2}em`,
      padding: "0 0.14em",
      borderRadius: "0.2em",
      background: active ? c.activeBackground : "transparent",
      color: active ? interpolateColors(since, [0, frames(a.colorFadeMs)], [rest, c.activeColor]) : rest,
      transform: `scale(${(emphasized ? c.emphasis.scale : 1) * (1 + (a.wordPopScale - 1) * pop)})`,
      fontFamily: emphasized ? style.fonts.emphasis.family : undefined,
      fontWeight: emphasized ? style.fonts.emphasis.weight : undefined,
      textTransform: emphasized && c.emphasis.uppercase ? "uppercase" : undefined,
    }}>
      {word.text}
    </span>
  );
};

const CaptionLayer = ({ captions, style }: CaptionProps) => {
  const { frame, fps, width, height, t, frames } = useTime();
  const group = activeGroup(captions.groups, "normal", t);
  if (!group) return null;
  const { caption: c, animation: a } = style;
  const enter = interpolate(frame - group.start * fps, [0, frames(a.groupInMs)], [0, 1], clamp);
  const active = group.words.findLastIndex((w) => w.start <= t);
  return (
    <div style={{
      position: "absolute", left: "50%", top: c.baselineY * height, width: c.maxWidth * width,
      transform: `translate(-50%, -100%) translateY(${(1 - enter) * a.groupInDistance * height}px)`,
      opacity: enter, textAlign: "center", color: c.color, textShadow: c.shadow,
      fontFamily: style.fonts.caption.family, fontWeight: style.fonts.caption.weight,
      fontSize: c.fontSize * width, lineHeight: c.lineHeight, letterSpacing: `${c.letterSpacing}em`,
    }}>
      {group.lines.map((line, i) => (
        <div key={i}>{line.map((w) => <Word key={w} word={group.words[w]} active={w === active} style={style} />)}</div>
      ))}
    </div>
  );
};

const HookLayer = ({ captions, style }: CaptionProps) => {
  const { frame, fps, width, height, t, frames } = useTime();
  const group = activeGroup(captions.groups, "hook", t);
  if (!group) return null;
  const { hook: h, animation: a } = style;
  const since = frame - group.start * fps;
  const raw = group.words.map((w) => w.text).join(" ");
  const text = h.uppercase ? raw.toUpperCase() : raw;
  const font = style.fonts.hook;
  const fitted = fitText({ text, withinWidth: h.maxWidth * width, fontFamily: font.family, fontWeight: font.weight }).fontSize;
  const grow = spring({ frame: since, fps, durationInFrames: frames(a.hookInMs), config: { damping: 12, stiffness: 180 } });
  const fadeIn = interpolate(since, [0, 3], [0, 1], clamp);
  const fadeOut = interpolate(group.end * fps - frame, [0, frames(a.hookOutMs)], [0, 1], clamp);
  const settle = [frames(a.hookSettleMs), frames(a.hookSettleMs + 200)];
  return (
    <div style={{ position: "absolute", top: h.topY * height, width: "100%", display: "flex", justifyContent: "center" }}>
      <div style={{
        background: interpolateColors(since, settle, [h.box.color, h.box.settledColor]), borderRadius: h.box.radius * width,
        padding: `${h.box.paddingY * width}px ${h.box.paddingX * width}px`,
        transform: `scale(${interpolate(grow, [0, 1], [a.hookInScale, 1])})`, opacity: Math.min(fadeIn, fadeOut),
        color: interpolateColors(since, settle, [h.accentColor, h.color]),
        fontFamily: font.family, fontWeight: font.weight, fontSize: Math.min(h.fontSize * width, fitted),
        lineHeight: 1.05, textShadow: h.shadow, whiteSpace: "nowrap",
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
