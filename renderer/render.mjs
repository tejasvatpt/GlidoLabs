// node render.mjs <props.json> <out.mp4>  — prints {"progress": n} lines for the backend
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

const here = path.dirname(fileURLToPath(import.meta.url));
const [propsPath, output] = process.argv.slice(2);
const inputProps = JSON.parse(await readFile(propsPath, "utf8"));

const serveUrl = await bundle({ entryPoint: path.join(here, "src/index.ts"), publicDir: path.join(here, "../styles") });
const composition = await selectComposition({ serveUrl, id: "CaptionedVideo", inputProps });

let last = -1;
await renderMedia({
  composition, serveUrl, inputProps, outputLocation: output, codec: "h264", crf: 18, concurrency: 2,
  onProgress: ({ progress }) => {
    const pct = Math.floor(progress * 100);
    if (pct !== last) console.log(JSON.stringify({ progress: (last = pct) / 100 }));
  },
});
