// node render.mjs <props.json> <video> <person-mask> <out.mp4>  — prints {"progress": n} lines for the backend.
// Chrome draws hooks | captions side by side on transparent images; FFmpeg composites
// video -> hooks -> speaker (video cut out by the mask) -> captions, so hooks sit behind the person.
// Eclipse only changes on hard cuts, so we draw one image per distinct caption state, not one per frame.
import { readdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { openBrowser, renderFrames, selectComposition } from "@remotion/renderer";

const here = path.dirname(fileURLToPath(import.meta.url));
const build = path.join(here, "build");

// Reuse the bundle in build/ unless the renderer source or the styles changed since it was built.
const newest = async (dir) => Math.max(0, ...await Promise.all((await readdir(dir, { recursive: true }))
  .map(async (f) => (await stat(path.join(dir, f))).mtimeMs)));
const builtAt = await stat(path.join(build, "index.html")).then((s) => s.mtimeMs, () => 0);
const fresh = builtAt > Math.max(await newest(path.join(here, "src")), await newest(path.join(here, "../styles")));
const serveUrl = fresh ? build : await bundle({ entryPoint: path.join(here, "src/index.ts"), publicDir: path.join(here, "../styles"), outDir: build });
if (process.argv[2] === "--bundle") process.exit(0);

const [propsPath, video, mask, output] = process.argv.slice(2);
const inputProps = JSON.parse(await readFile(propsPath, "utf8"));
const frames = path.join(path.dirname(output), "frames");
const report = (p) => console.log(JSON.stringify({ progress: p }));
const chromiumOptions = { gl: "angle" };

// Chrome can take >25 s to start when RAM is tight; retry instead of failing the export
const launch = async (tries = 3) => {
  try {
    return await openBrowser("chrome", { chromiumOptions });
  } catch (error) {
    if (tries <= 1) throw error;
    return launch(tries - 1);
  }
};
const puppeteerInstance = await launch();
const full = await selectComposition({ serveUrl, id: "CaptionedVideo", inputProps, puppeteerInstance });
await rm(frames, { recursive: true, force: true });

// What is on screen at frame f (mirrors CaptionedVideo.tsx): visible groups and which of their words are spoken.
const { groups } = inputProps.captions;
const stateAt = (f) => {
  const t = f / full.fps;
  return groups.filter((g) => g.start <= t && t < g.end)
    .map((g) => `${g.id}:${g.words.map((w) => +(w.start <= t && t < w.end)).join("")}`).join("|");
};
const segments = [];
for (let f = 0; f < full.durationInFrames; f++) {
  const state = stateAt(f);
  if (segments.at(-1)?.state === state) segments.at(-1).frames++;
  else segments.push({ state, first: f, frames: 1 });
}
const unique = [...new Map(segments.map((s) => [s.state, s.first])).values()];
const stateProps = { ...inputProps, frames: unique };
const composition = await selectComposition({ serveUrl, id: "CaptionedVideo", inputProps: stateProps, puppeteerInstance });

let last = -1;
await renderFrames({
  composition, serveUrl, inputProps: stateProps, outputDir: frames, imageFormat: "png", concurrency: 2,
  timeoutInMilliseconds: 120000, chromiumOptions, puppeteerInstance, onStart: () => {},
  onFrameUpdate: (done) => {
    const pct = Math.floor((done / unique.length) * 80);
    if (pct !== last) report((last = pct) / 100);
  },
});
await puppeteerInstance.close({ silent: true });

// frame i of the state render is state i; FFmpeg's concat list holds each image for its segment's duration
const files = (await readdir(frames)).filter((f) => f.endsWith(".png")).sort();
const states = [...new Set(segments.map((s) => s.state))];
const entry = (state) => `file '${path.join(frames, files[states.indexOf(state)]).replaceAll("\\", "/")}'`;
const list = segments.map((s) => `${entry(s.state)}\nduration ${s.frames / full.fps}`);
await writeFile(path.join(frames, "list.txt"), `${list.join("\n")}\n${entry(segments.at(-1).state)}\n`);

const [w, h] = [composition.width / 2, composition.height];
const graph = [
  "[1:v]split[l1][l2]", `[l1]crop=${w}:${h}:0:0[hooks]`, `[l2]crop=${w}:${h}:${w}:0[caps]`,
  `[2:v]scale=${w}:${h}:flags=bicubic,format=gray,boxblur=1[mask]`, "[0:v]split[base][src]",
  "[base][hooks]overlay=format=auto:eof_action=pass[behind]", "[src][mask]alphamerge[person]",
  "[behind][person]overlay=format=auto[front]", "[front][caps]overlay=format=auto:eof_action=pass,format=yuv420p[out]",
].join(";");
const ffmpeg = spawnSync("ffmpeg", [
  "-y", "-v", "error", "-i", video, "-f", "concat", "-safe", "0", "-i", path.join(frames, "list.txt"),
  "-i", mask, "-filter_complex", graph, "-map", "[out]", "-map", "0:a?",
  "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output,
], { stdio: "inherit" });
await rm(frames, { recursive: true, force: true });
if (ffmpeg.status !== 0) process.exit(ffmpeg.status ?? 1);
report(1);
