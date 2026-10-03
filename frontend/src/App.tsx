import { useEffect, useState } from "react";

type Job = { id: string; status: string; progress: number; error: string | null };

const STAGES: Record<string, string> = {
  queued: "Getting ready (first run loads the AI models)", preparing: "Converting to vertical UGC layout",
  transcribing: "Transcribing speech", captioning: "Finding the speaker and planning captions", rendering: "Rendering video",
};

const getJob = async (id: string): Promise<Job> => {
  const res = await fetch(`/api/jobs/${id}`);
  if (!res.ok) throw new Error("Job not found");
  return res.json();
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
  const busy = job && !["done", "error"].includes(job.status);

  useEffect(() => {
    const id = location.hash.match(/job=(\w+)/)?.[1];
    if (id) getJob(id).then(setJob).catch(() => (location.hash = ""));
  }, []);

  useEffect(() => {
    if (job) location.hash = `job=${job.id}`;
  }, [job?.id]);

  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(() => getJob(job.id).then(setJob).catch((e) => setError(e.message)), 1200);
    return () => clearInterval(timer);
  }, [busy, job?.id]);

  const start = async () => {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("script", script);
    setError("");
    try {
      setJob({ id: await upload(form, setUploadProgress), status: "queued", progress: 0, error: null });
    } catch (e) {
      setError((e as Error).message);
    }
    setUploadProgress(null);
  };

  const reset = () => {
    setFile(null);
    setJob(null);
    setError("");
    setScript("");
    history.replaceState(null, "", location.pathname);
  };

  return (
    <main>
      <header>
        <h1>CapSync</h1>
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
              <summary>I have the script (AI-generated voice-over)</summary>
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
            <strong>{STAGES[job.status]}</strong>
            <div className="bar"><div style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
            <span>{Math.round(job.progress * 100)}%</span>
          </div>
        )}

        {job?.status === "done" && (
          <div className="preview">
            <video src={`/api/jobs/${job.id}/video`} controls autoPlay playsInline />
            <div className="actions">
              <a className="button" href={`/api/jobs/${job.id}/download`} download>Download MP4</a>
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
