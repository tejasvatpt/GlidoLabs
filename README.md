# Glido Labs — AI Caption Engine

Upload a video, get word-timed Roman-Hinglish captions in the **Eclipse** style, preview them live, export an MP4.

```
Video ─► FFmpeg ─► ASR / script ─► Word[] + timings ─► features ─► roles ─► groups ─► captions.json ─► Remotion ─► MP4
```

## Quick start

Requirements: Python 3.12+, Node 20+, FFmpeg on PATH, ideally an NVIDIA GPU with the CUDA build of PyTorch
(`pip install torch --index-url https://download.pytorch.org/whl/cu126`). A 30 s clip transcribes in ~15 s on an
RTX 2050 (2.3 GB VRAM); on CPU it needs ~3 GB of free RAM and a few minutes.

```bash
cp .env.example .env
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt   # macOS/Linux: backend/.venv/bin/pip
npm install
npm run build --workspace frontend
```

Run (Windows PowerShell; 5.1 has no `&&`):

```powershell
cd backend
.\.venv\Scripts\uvicorn app.main:app --port 8000
```

Open http://127.0.0.1:8000. The server loads the Apex model at startup (~1.6 GB download the first time).
Development: `npm run dev --workspace frontend` (Vite, proxies the API) and `npm run studio --workspace renderer`.
Tests: `cd backend && .venv/Scripts/python -m pytest` (`-m "not slow"` skips the model test).

## Structure

```
backend/app/
  main.py, jobs.py, config.py      API, one background worker, settings + style loading
  media/        probe.py (ffprobe, WAV)  ingest.py (validate, job folder)  audio.py (loudness, voiced frames)
  transcription/ sources.py (Apex ASR, script path)  cleanup.py (respell, snap to speech, align)  spelling.json
  captions/     features.py → emphasis.py → segmenter.py (+ layout.py text measuring) → build.py
  rendering.py  runs renderer/render.mjs
renderer/src/   CaptionedVideo.tsx (the Eclipse renderer), Root.tsx, types.ts
frontend/src/   App.tsx (upload → progress → live preview → export)
styles/eclipse/ style.json + bundled OFL fonts
```

The renderer only reads `captions.json` + `style.json` + the video; it knows nothing about ASR or scoring.

### Two input paths

- **Uploaded video (no script):** Whisper-Hindi2Hinglish-Apex transcribes in Roman script with word timestamps, then
  `spelling.json` maps Apex spellings to common social-media Hinglish (*mainne → maine, yah → ye, lie → liye*).
- **Glido-generated video (script known):** caption text is the script word for word; audio only supplies timing
  (script words are matched onto heard-word timestamps). In production the TTS engine's word boundaries plug in here.

Both paths snap every word onto voiced audio (`media/audio.py`), so no caption appears over silence, even if speech
starts seconds into the video. Another ASR (AssemblyAI, Sarvam, a forced aligner) only has to return `Word[]`.

### Caption intelligence

1. **Features** per word: loudness relative to neighbouring words, stretch (seconds per letter), pause before, and
   lexical salience (length + English rarity from `wordfreq`; words barely attested in English, i.e. romanised Hindi, stay neutral).
2. **Roles:** weighted score from `style.json`. Prosody can promote a word but never demote it (speakers often say key
   words quieter). A **hook** must be a strong content word said only once in the video, within a per-minute budget and
   a minimum gap; strong content words become **emphasis**. Optional `force_hooks` pins keywords. No word lists of hooks.
3. **Grouping:** breaks on pauses ≥ 0.35 s, sentence punctuation, max words, rendered width and around hooks; merges
   orphans, closes short gaps, guarantees hook read time. Line breaks use pixel widths measured with the real fonts.

### Eclipse style (measured frame by frame)

- Captions: Montserrat Bold, 5.8% of width, baseline at 80%; the spoken word turns yellow with a soft pill only
  while it is spoken; emphasis words switch to Anton uppercase. Groups and highlights switch on hard cuts.
- Hooks: Anton uppercase fitted to 86% width near the top; yellow on a translucent yellow box for 567 ms (17 frames
  at 30 fps), then a hard cut to white without the box.

All values are fractions of the frame in `styles/eclipse/style.json`; a new style is a new folder, no code changes.

## Technology decisions

| Area | Current (free, local) | Premium upgrade | Why |
| --- | --- | --- | --- |
| ASR | [Whisper-Hindi2Hinglish-Apex](https://huggingface.co/Oriserve/Whisper-Hindi2Hinglish-Apex) (Apache-2.0) | ElevenLabs Scribe, AssemblyAI, Sarvam Saaras | Only open model found that outputs Roman Hinglish; fits a 4 GB GPU |
| Word timing | Whisper timestamps + voiced-audio snapping; script mapping | CTC forced alignment, TTS word boundaries | No extra model |
| Rendering | [Remotion](https://www.remotion.dev/docs/license) 4.x (pinned) | Remotion Lambda | One React composition for live preview and MP4; free for individuals and companies of up to 3 people |
| Media | FFmpeg | — | Probe, audio, encode |
| Fonts | Montserrat, Anton (SIL OFL, bundled) | — | Closest open match to Eclipse |
| Storage | Local `storage/jobs/` (24 h cleanup) | S3 / R2 | No database needed |

Model-author benchmarks use different test sets and are not comparable; the numbers below are our own small test.

## Results on the reference

First 20 s of `Eclipse.mp4`, ground truth typed from its burnt-in captions (`backend/tests/data/eclipse_first_20s.txt`):

| Check | Result |
| --- | --- |
| Script | Roman only |
| Word error rate | 0.286 raw Apex → 0.036 after the spelling map (the map was partly built from this clip, so expect less on new videos) |
| Word timing | within ~±0.2 s of the reference's highlight changes |
| Speed | 3.9 s for 20 s of audio on an RTX 2050 |
| Hooks on the full clip | OBSIDIAN (11.9 s) and PISCES (22.7 s), the same hooks Eclipse uses, plus FLEXIBLE (Eclipse emphasises it) |

Apex ships without Whisper's word-timing heads, so it reuses large-v3-turbo's (same architecture). Encoder attention
maps are switched off during word timing, cutting VRAM from 5.2 to 2.3 GB.

## Samples

- `samples/demo_input.mp4` — Hinglish script read by an offline Indian-English voice over drone footage (`samples/make_tts_sample.ps1`).
- `samples/demo_output.mp4` — rendered through the script path; `samples/demo_output_asr.mp4` — through the ASR path.

The Eclipse reference already has captions burned in, so it is used only as the style reference.

## Limitations

- The spelling map covers common Apex spellings only; new words keep Apex's spelling.
- Whisper timestamps can drift ~0.1–0.2 s on fast speech; a forced aligner is the next upgrade.
- Hooks are heuristic; very flat delivery or very short clips yield fewer hooks (tune `hookThreshold`).
