import { useEffect, useState } from "react";
import { AbsoluteFill, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { CaptionGroup, CaptionProps, CaptionWord, Style } from "./types";

// Two transparent layers side by side: hooks (left half) go behind the speaker, captions (right half) go on top.
// FFmpeg splits them and composites: video -> hooks -> speaker cut-out -> captions. Eclipse uses hard cuts only.

type LayerProps = CaptionProps & { t: number; width: number; height: number };

const activeGroup = (groups: CaptionGroup[], layer: CaptionGroup["layer"], t: number) =>
  groups.find((g) => g.layer === layer && g.start <= t && t < g.end);

const spoken = (w: CaptionWord, t: number) => w.start <= t && t < w.end;

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

const CaptionLayer = ({ captions, style, t, width, height }: LayerProps) => {
  const group = activeGroup(captions.groups, "normal", t);
  if (!group) return null;
  const c = style.caption;
  return (
    <div style={{
      position: "absolute", left: width / 2, top: c.baselineY * height, width: c.maxWidth * width,
      transform: "translate(-50%, -100%)", textAlign: "center", color: c.color, textShadow: c.shadow,
      fontFamily: style.fonts.caption.family, fontWeight: style.fonts.caption.weight,
      fontSize: c.fontSize * width, lineHeight: c.lineHeight,
    }}>
      {group.lines.map((line, i) => (
        <div key={i}>{line.map((w) => <Word key={w} word={group.words[w]} active={spoken(group.words[w], t)} style={style} />)}</div>
      ))}
    </div>
  );
};

// White while waiting, yellow on the translucent box only while the word is spoken (as in the reference).
const HookLayer = ({ captions, style, t, width, height }: LayerProps) => {
  const group = activeGroup(captions.groups, "hook", t);
  if (!group?.position) return null;
  const { hook: h, fonts } = style;
  const word = group.words[0];
  const { x, y, align, font_size } = group.position;
  const live = spoken(word, t);
  const padX = h.box.paddingX * width, padY = h.box.paddingY * width;
  return (
    <div style={{
      position: "absolute", top: y * height - padY, left: x * width - (align === "left" ? padX : 0),
      transform: align === "center" ? "translateX(-50%)" : undefined,
      padding: `${padY}px ${padX}px`, borderRadius: h.box.radius * width, background: live ? h.box.color : "transparent",
      color: live ? h.accentColor : h.color, textShadow: live ? "none" : h.shadow, whiteSpace: "nowrap",
      fontFamily: fonts.hook.family, fontWeight: fonts.hook.weight, fontSize: font_size * width, lineHeight: 1,
    }}>
      {word.display ?? word.text.toUpperCase()}
    </div>
  );
};

export const CaptionedVideo = (props: CaptionProps) => {
  const fontsLoaded = useFonts(props.style);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { width, height } = props.captions.video;
  const layer = { ...props, t: frame / fps, width, height };
  return (
    <AbsoluteFill>
      <div style={{ position: "absolute", left: 0, width, height, overflow: "hidden" }}>
        {fontsLoaded && <HookLayer {...layer} />}
      </div>
      <div style={{ position: "absolute", left: width, width, height, overflow: "hidden" }}>
        {fontsLoaded && <CaptionLayer {...layer} />}
      </div>
    </AbsoluteFill>
  );
};
