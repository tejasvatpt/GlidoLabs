// node render.mjs <props.json> <input-video> <out.mp4>  — prints {"progress": n} lines for the backend.
// Chrome draws only the captions (transparent PNGs, GPU via ANGLE); FFmpeg decodes the original video and overlays them.
import { readdir, readFile, rm } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { openBrowser, renderFrames, selectComposition } from "@remotion/renderer";

const here = path.dirname(fileURLToPath(import.meta.url));
const [propsPath, input, output] = process.argv.slice(2);
const inputProps = { ...JSON.parse(await readFile(propsPath, "utf8")), videoSrc: "" };
const frames = path.join(path.dirname(output), "frames");
const report = (p) => console.log(JSON.stringify({ progress: p }));

const chromiumOptions = { gl: "angle" };
const [serveUrl, puppeteerInstance] = await Promise.all([
  bundle({ entryPoint: path.join(here, "src/index.ts"), publicDir: path.join(here, "../styles") }),
  openBrowser("chrome", { chromiumOptions }),
]);
const composition = await selectComposition({ serveUrl, id: "CaptionedVideo", inputProps, puppeteerInstance });
await rm(frames, { recursive: true, force: true });

let last = -1;
await renderFrames({
  composition, serveUrl, inputProps, outputDir: frames, imageFormat: "png", concurrency: 4,
  chromiumOptions, puppeteerInstance, onStart: () => {},
  onFrameUpdate: (done) => {
    const pct = Math.floor((done / composition.durationInFrames) * 90);
    if (pct !== last) report((last = pct) / 100);
  },
});

await puppeteerInstance.close({ silent: true });
const digits = (await readdir(frames))[0].match(/\d+/)[0].length;
const ffmpeg = spawnSync("ffmpeg", [
  "-y", "-v", "error", "-i", input, "-framerate", String(composition.fps), "-i", path.join(frames, `element-%0${digits}d.png`),
  "-filter_complex", "[0:v][1:v]overlay=format=auto:eof_action=pass,format=yuv420p",
  "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output,
], { stdio: "inherit" });
await rm(frames, { recursive: true, force: true });
if (ffmpeg.status !== 0) process.exit(ffmpeg.status ?? 1);
report(1);
