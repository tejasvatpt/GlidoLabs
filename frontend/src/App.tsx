import { useEffect, useState } from "react";
import { Player } from "@remotion/player";
import { CaptionedVideo } from "renderer/src/CaptionedVideo";
import type { Captions, Style } from "renderer/src/types";

type Job = { id: string; status: string; progress: number; error: string | null };

const STAGE_LABELS: Record<string, string> = {
  queued: "Getting ready (first run loads the AI model)", extracting: "Extracting audio", transcribing: "Transcribing speech",
  captioning: "Building captions", rendering: "Rendering video",
};

const getJson = async <T,>(url: string, init?: RequestInit): Promise<T> => {
  const res = await fetch(url, init);
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail ?? "Request failed");
  return body;
};

const upload = (form: FormData, onProgress: (p: number) => void) =>
  new Promise<string>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/jobs");
    xhr.upload.onprogress = (e) => onProgress(e.loaded / e.total);
    xhr.onload = () => {
      const body = JSON.parse(xhr.responseText);
      xhr.status < 300 ? resolve(body.job_id) : reject(new Error(body.detail ?? "Upload failed"));
    };
    xhr.onerror = () => reject(new Error("Upload failed. Is the backend running?"));
    xhr.send(form);
  });

export const App = () => {
  const [file, setFile] = useState<File | null>(null);
  const [script, setScript] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<{ captions: Captions; style: Style } | null>(null);

  const busy = job && !["ready", "done", "error"].includes(job.status);

  useEffect(() => {
    const id = location.hash.match(/job=(\w+)/)?.[1];
    if (id) getJson<Job>(`/api/jobs/${id}`).then(setJob).catch(() => (location.hash = ""));
  }, []);

  useEffect(() => {
    if (job) location.hash = `job=${job.id}`;
  }, [job?.id]);

  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => getJson<Job>(`/api/jobs/${job.id}`).then(setJob).catch((e) => setError(e.message)), 1200);
    return () => clearInterval(timer);
  }, [busy, job?.id]);

  useEffect(() => {
    if (!job || !["ready", "done"].includes(job.status) || preview) return;
    getJson<Captions>(`/api/jobs/${job.id}/captions`)
      .then(async (captions) => setPreview({ captions, style: await getJson<Style>(`/api/styles/${captions.style}`) }))
      .catch((e) => setError(e.message));
  }, [job?.status]);

  const start = async () => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("script", script);
    setError("");
    setPreview(null);
    try {
      const id = await upload(form, setUploadProgress);
      setJob({ id, status: "queued", progress: 0, error: null });
    } catch (e) {
      setError((e as Error).message);
    }
    setUploadProgress(null);
  };

  const exportVideo = async () => {
    await getJson(`/api/jobs/${job!.id}/export`, { method: "POST" }).catch((e) => setError(e.message));
    setJob({ ...job!, status: "rendering", progress: 0 });
  };

  const reset = () => {
    [setFile(null), setJob(null), setPreview(null), setError(""), setScript("")];
    history.replaceState(null, "", location.pathname);
  };
  const video = preview?.captions.video;

  return (
    <main>
      <header>
        <h1>Glido Labs</h1>
        <p>AI captions in the Eclipse style</p>
      </header>

      <section className="card">
        {!job && (
          <>
            <label className={`drop ${file ? "has-file" : ""}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); setFile(e.dataTransfer.files[0] ?? null); }}>
              <input type="file" accept="video/mp4,video/quicktime,video/webm,video/x-matroska"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              {file ? <><strong>{file.name}</strong><span>{(file.size / 1048576).toFixed(1)} MB</span></>
                : <><strong>Drop a video here</strong><span>or click to choose MP4, MOV, WebM or MKV</span></>}
            </label>
            <details>
              <summary>I have the script (Glido-generated video)</summary>
              <textarea rows={4} value={script} onChange={(e) => setScript(e.target.value)}
                placeholder="Paste the exact script. Captions will use it word for word; audio only sets the timing." />
            </details>
            <button disabled={!file || uploadProgress !== null} onClick={start}>
              {uploadProgress !== null ? `Uploading ${Math.round(uploadProgress * 100)}%` : "Generate captions"}
            </button>
          </>
        )}

        {busy && (
          <div className="status">
            <strong>{STAGE_LABELS[job.status]}</strong>
            <div className="bar"><div style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
            <span>{job.status === "transcribing" ? "This can take a minute on CPU." : `${Math.round(job.progress * 100)}%`}</span>
          </div>
        )}

        {preview && video && (
          <div className="preview">
            <Player component={CaptionedVideo} controls
              inputProps={{ videoSrc: `/media/${job!.id}/input`, ...preview }}
              durationInFrames={Math.ceil(video.duration * video.fps)} fps={video.fps}
              compositionWidth={video.width} compositionHeight={video.height}
              style={{ width: "100%", maxHeight: "68vh", aspectRatio: `${video.width} / ${video.height}` }} />
            <div className="actions">
              {job?.status === "done"
                ? <a className="button" href={`/api/jobs/${job.id}/download`} download>Download MP4</a>
                : !busy && <button onClick={exportVideo}>Export MP4</button>}
              <button className="secondary" onClick={reset}>New video</button>
            </div>
          </div>
        )}

        {(error || job?.status === "error") && (
          <div className="error">
            <span>{error || job?.error}</span>
            <button className="secondary" onClick={reset}>Try another video</button>
          </div>
        )}
      </section>
    </main>
  );
};
