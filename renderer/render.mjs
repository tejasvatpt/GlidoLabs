// node render.mjs <props.json> <video> <person-mask> <out.mp4>  — prints {"progress": n} lines for the backend.
// Chrome draws hooks | captions side by side on transparent frames; FFmpeg composites
// video -> hooks -> speaker (video cut out by the mask) -> captions, so hooks sit behind the person.
import { readdir, readFile, rm } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { openBrowser, renderFrames, selectComposition } from "@remotion/renderer";

const here = path.dirname(fileURLToPath(import.meta.url));
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
const [serveUrl, puppeteerInstance] = await Promise.all([
  bundle({ entryPoint: path.join(here, "src/index.ts"), publicDir: path.join(here, "../styles") }),
  launch(),
]);
const composition = await selectComposition({ serveUrl, id: "CaptionedVideo", inputProps, puppeteerInstance });
await rm(frames, { recursive: true, force: true });

let last = -1;
await renderFrames({
  composition, serveUrl, inputProps, outputDir: frames, imageFormat: "png", concurrency: 2, timeoutInMilliseconds: 120000,
  chromiumOptions, puppeteerInstance, onStart: () => {},
  onFrameUpdate: (done) => {
    const pct = Math.floor((done / composition.durationInFrames) * 85);
    if (pct !== last) report((last = pct) / 100);
  },
});
await puppeteerInstance.close({ silent: true });

const [w, h] = [composition.width / 2, composition.height];
const digits = (await readdir(frames))[0].match(/\d+/)[0].length;
const graph = [
  "[1:v]split[l1][l2]", `[l1]crop=${w}:${h}:0:0[hooks]`, `[l2]crop=${w}:${h}:${w}:0[caps]`,
  `[2:v]scale=${w}:${h}:flags=bicubic,format=gray,boxblur=1[mask]`, "[0:v]split[base][src]",
  "[base][hooks]overlay=format=auto:eof_action=pass[behind]", "[src][mask]alphamerge[person]",
  "[behind][person]overlay=format=auto[front]", "[front][caps]overlay=format=auto:eof_action=pass,format=yuv420p[out]",
].join(";");
const ffmpeg = spawnSync("ffmpeg", [
  "-y", "-v", "error", "-i", video, "-framerate", String(composition.fps), "-i", path.join(frames, `element-%0${digits}d.png`),
  "-i", mask, "-filter_complex", graph, "-map", "[out]", "-map", "0:a?",
  "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output,
], { stdio: "inherit" });
await rm(frames, { recursive: true, force: true });
if (ffmpeg.status !== 0) process.exit(ffmpeg.status ?? 1);
report(1);
