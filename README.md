# Glido Labs — AI Caption Engine

Upload a video, get word-timed Roman-Hinglish captions in the **Eclipse** style, preview them live, export an MP4.

```
Video ─► FFmpeg ─► ASR / script ─► Word[] + timings ─► features ─► roles ─► groups ─► captions.json ─► Remotion ─► MP4
```

## Quick start

Requirements: Python 3.12+, Node 20+, FFmpeg on PATH. An NVIDIA GPU is optional (CPU works, slower).

```bash
cp .env.example .env
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt   # macOS/Linux: backend/.venv/bin/pip
npm install
npm run build --workspace frontend
cd backend && .venv/Scripts/uvicorn app.main:app --port 8000
```

Open http://127.0.0.1:8000. The first transcription downloads the Apex model (~1.6 GB) from Hugging Face.

For development, run `npm run dev --workspace frontend` (Vite on :5173, proxies the API) and `npm run studio --workspace renderer` (Remotion Studio for tuning the style).

Tests: `cd backend && .venv/Scripts/python -m pytest` (`-m "not slow"` skips the model test).

## How it works

| Layer | Responsibility | Code |
| --- | --- | --- |
| Media | validate, ffprobe metadata, 16 kHz mono WAV | `backend/app/media/` |
| Transcription | `Word[]` with timings from a replaceable source | `backend/app/transcription/` |
| Caption engine | features → emphasis/hook roles → caption groups → `captions.json` | `backend/app/captions/` |
| Style | every visual, animation and engine value | `styles/eclipse/style.json` |
| Renderer | draws captions over the video, frame-exact | `renderer/src/CaptionedVideo.tsx` |
| API | jobs, upload, status, export, download | `backend/app/main.py`, `jobs.py` |
| UI | upload → progress → live preview → export | `frontend/src/App.tsx` |

The modules only talk through data. The renderer reads `captions.json` + `style.json` + the video and knows nothing about ASR or scoring.

### Two input paths

- **Uploaded video (no script)** → `ApexSource`: Whisper-Hindi2Hinglish-Apex transcribes in Roman script with word timestamps.
- **Glido-generated video (script known)** → `ScriptSource`: caption text is the script, word for word; audio only supplies timing (script words are matched onto heard-word timestamps, gaps interpolated). In production, the TTS engine's own word-boundary output plugs in here and no ASR runs at all.

Adding AssemblyAI, Sarvam or a forced aligner means adding one class with `transcribe(wav, script) -> Transcript`.

### Caption intelligence (pause-aware breaks + audio-energy hooks)

1. **Features** per word from the WAV: loudness (RMS dB over 25 ms frames), stretch (seconds per letter), pause before, lexical weight (length, not a stopword). Loudness, stretch and pause become robust z-scores (median/MAD) relative to the speaker.
2. **Score** = weighted sum (weights in `style.json`). Top words become **hooks**, limited by a per-minute budget and a minimum gap; strong content words become **emphasis**; the rest are normal. Optional `force_hooks` lets a user pin keywords. No word is hard-coded.
3. **Grouping** breaks captions on pauses ≥ 0.35 s, sentence punctuation, max words/characters, and around hooks; then merges orphans, closes small gaps (no flicker), guarantees hook read time and balances two-line breaks.

### Eclipse style

Measured from the reference frame by frame and stored as fractions of the frame, so it works at any resolution:

- Normal captions: Montserrat Bold, white, ~5.8% of width, baseline at 80% height; active word turns yellow with a soft pill; emphasis words switch to Anton uppercase.
- Hooks: Anton uppercase fitted to ~86% width near the top, pop in yellow on a translucent yellow box, then settle to white as the box fades.

A new style is a new folder in `styles/` with its own `style.json` and fonts; no code changes.

## Technology decisions

| Area | Current (free, local) | Premium upgrade | Why this choice |
| --- | --- | --- | --- |
| ASR | [Oriserve Whisper-Hindi2Hinglish-Apex](https://huggingface.co/Oriserve/Whisper-Hindi2Hinglish-Apex) (Apache-2.0) | ElevenLabs Scribe, AssemblyAI, Sarvam Saaras | Only open model found that outputs Roman-script Hinglish; fits 4 GB VRAM in fp16 |
| Word timing | Whisper word timestamps; script mapping | CTC forced alignment (MMS), TTS word boundaries | No extra model download; aligner is a drop-in source |
| Rendering | [Remotion](https://www.remotion.dev/docs/license) 4.x (pinned) | Remotion Lambda for cloud renders | Same React composition for live preview and MP4; free for individuals and companies of up to 3 people |
| Media | FFmpeg | — | Probe, audio, encode |
| Fonts | Montserrat, Anton (SIL OFL, bundled) | — | Closest open match to Eclipse |
| Storage | Local `storage/jobs/` (24 h cleanup) | S3 / R2 | No database needed |

Benchmarks quoted by model authors use different test sets and are not comparable with each other; the measurement below is our own small test.

## ASR check on the reference

<!-- filled from tests/test_transcription.py -->

## Samples

- `samples/demo_input.mp4` — clean clip: Hinglish script read by an offline Indian-English voice over drone footage (`samples/make_tts_sample.ps1`).
- `samples/demo_output.mp4` — rendered by the app.

The Eclipse reference already has captions burned in, so it is used only as the style reference.

## Limitations

- CPU transcription of a 1-minute clip takes a few minutes; a CUDA build of PyTorch makes it seconds.
- Whisper timestamps can drift by ~0.1–0.2 s on fast speech; a forced aligner is the next upgrade.
- Hook selection is heuristic; very flat delivery yields fewer hooks (tune `hookThreshold`).
