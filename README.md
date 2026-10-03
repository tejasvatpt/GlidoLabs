




# Glido Labs Assignment

## CapSync — Hinglish Caption Engine

CapSync puts **animated captions** on your videos, automatically.

You upload a video → it turns it into a vertical **UGC-style** clip → listens to the speech → writes the words in **Roman Hinglish** (like *"bhai ye bahut accha hai"*) → adds **Eclipse-style** captions, with the big highlighted words placed **behind the speaker** → you preview and download the MP4.

It works with **English, Hindi and Hinglish** (Hindi + English mixed), and everything runs **free on your own computer**.

### 🎬 Demo

https://github.com/user-attachments/assets/da5d7757-ca01-403c-8542-e104d33fb578
[![CapSync output: captions in front, hook word behind the speaker]]([samples/demo_output.mp4](https://github.com/user-attachments/assets/da5d7757-ca01-403c-8542-e104d33fb578))

*Output for `samples/demo_input.mp4`: notice the big yellow word sits behind the character's hair. Click for the full video.*

---

## Quick start

### 1. What you need

| Tool | Why | Get it |
| --- | --- | --- |
| **Python 3.12+** | runs the backend and the AI model | [python.org](https://www.python.org/downloads/) |
| **Node.js 20+** | runs the caption renderer and the website | [nodejs.org](https://nodejs.org/) |
| **FFmpeg** | reads and writes video/audio | [ffmpeg.org](https://ffmpeg.org/download.html) (must work when you type `ffmpeg` in a terminal) |
| **Git** | to copy this repo | [git-scm.com](https://git-scm.com/) |
| NVIDIA GPU *(optional, recommended)* | makes transcription much faster | any card with 4 GB+ |

> No GPU? It still works on CPU, just slower (needs ~3 GB of free RAM).

### 2. Copy the repo

```bash
git clone https://github.com/tejasvatpt/GlidoLabs.git
cd GlidoLabs
```

### 3. Set up the backend (Python)

```bash
cp .env.example .env
python -m venv backend/.venv
```

Activate it:

- **Windows (PowerShell):** `backend\.venv\Scripts\Activate.ps1`
- **Mac / Linux:** `source backend/.venv/bin/activate`

Install the packages:

```bash
pip install -r backend/requirements.txt
pip install --no-deps silero-vad
```

**Have an NVIDIA GPU?** Also run this (it swaps in the GPU version of PyTorch):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu126
```

### 4. Set up the website and renderer (Node)

```bash
npm install
npm run build --workspace frontend
```

### 5. Run it

**Windows:** just double-click **`start.bat`** in the project folder.

**Mac / Linux:**

```bash
cd backend
uvicorn app.main:app --port 8000
```

Open **http://127.0.0.1:8000** in your browser. That's it! 🎉

> The first start downloads the speech model (~1.6 GB) once. Wait until the terminal is quiet (about 2 minutes), then upload a video.

### 6. Use it

1. Drop a video (MP4, MOV, WebM or MKV).
2. Click **Generate captions** and wait (about 1 minute for a 30 s clip).
3. Watch the **preview**: it's the finished video.
4. Click **Download MP4**.

Want to test quickly? Try `samples/demo_input.mp4`.

---

## How it works (the simple version)

```
Video → make it vertical (UGC) → AI writes the words + timings → find the speaker → plan captions and hooks → draw → stack layers → MP4
```

The project has **5 parts**, and each one does one job:

| Part | Folder | What it does |
| --- | --- | --- |
| 🎧 **Listener** | `backend/app/transcription` | Turns speech into words with exact timings |
| 🧍 **Speaker finder** | `backend/app/media` | Makes the video vertical and cuts out the person in every frame |
| 🧠 **Caption brain** | `backend/app/captions` | Decides how words are grouped, which word is highlighted, which words become big "hooks", and where each hook goes |
| 🎨 **Renderer** | `renderer/` | Draws the captions in the Eclipse style and makes the MP4 |
| 🖥️ **Website + API** | `frontend/`, `backend/app/main.py` | Upload, progress bar, preview, download |

They talk to each other through one simple file: **`captions.json`** (the words, their times and their roles).
So you can swap any part without breaking the others.

---

## The modules, one by one

### 🎧 Listener — speech to words

**Model:** [Whisper-Hindi2Hinglish-Apex](https://huggingface.co/Oriserve/Whisper-Hindi2Hinglish-Apex) (free, open source)

**Why this model?**
- It's built on OpenAI's Whisper and **fine-tuned on Indian Hindi + English speech**.
- It writes Hindi in **Roman letters** (*"pehli baar"*), not Devanagari (*"पहली बार"*), and it doesn't translate into English.
- That's exactly how people write Hinglish on social media, which is what we want.
- It's small enough to run on a 4 GB laptop GPU.

**Extra helpers:**
- **Spelling fix:** turns model spellings into common ones (*mainne → maine, yah → ye, lie → liye*).
- **Voice detector (Silero VAD):** finds where someone is *actually talking*, so captions never show up over music, rain or silence, and disappear when speech stops.

**Already have the script?** (e.g. an AI-generated video where you wrote the voice-over)
Paste it in the "I have the script" box. The captions use your exact words; the audio is only used for timing.

### 🧠 Caption brain — how captions are planned

For every word, it looks at:

- **Loudness** compared to nearby words
- **How long** the word is stretched
- **Pauses** before it
- **How meaningful** the word is (long, rare words like *"obsidian"* matter more than *"hai"*)

Then it decides:

| Role | What you see |
| --- | --- |
| **Normal** | white text at the bottom; turns yellow while it's spoken |
| **Emphasis** | bigger, uppercase word inside the caption |
| **Hook** | a huge word **behind the speaker's head** (like **OBSIDIAN**); white first, **yellow on a box while it's spoken** |

Captions are split at natural **pauses**, at the end of sentences, or when they get too wide for the screen.
Numbers become digits in hooks (*baarah* → **12**), like the reference.

### 🧍 Speaker finder: how the word goes *behind* the person

1. **UGC layout:** every upload becomes full-screen vertical 1080×1920. Black bars are removed and the crop follows the speaker.
2. **Cut-out:** [MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/vision/image_segmenter) (free, runs locally) makes a black-and-white **mask** of the person for every frame.
3. **Hook placement:** the mask tells us where the head is. Long words go centred above the head, short words to the left at head height, always low enough that the head covers part of the word.
4. **Layer stack:** FFmpeg stacks four layers per frame:

```
4. normal captions      ← on top
3. the person (cut out using the mask)
2. hook word + yellow box
1. original video       ← bottom
```

The person layer covers the hook wherever the person is, so the word looks like it's **behind** them.

### 🎨 Renderer — drawing the captions

Built with **[Remotion](https://www.remotion.dev/)** (React for videos).

- It draws the **hooks** and the **captions** as two transparent layers, in one pass.
- **FFmpeg** stacks them with the video and the person cut-out (see above). The preview is the finished video, so what you see is exactly what you download.

### 🎨 The Eclipse style

All the looks live in one file: **`styles/eclipse/style.json`**. It was copied frame by frame from the reference video:

- Captions: **Montserrat Bold**, 72 px on a 1080 px frame, wide word gaps, near the bottom; the spoken word turns **yellow** on a soft pill.
- Hooks: **Anton**, huge, behind the speaker; **white** until the word is spoken, then **yellow on a near full-width translucent yellow box**.
- Both fonts are free (SIL OFL) and included.
- Sizes, positions and timings were measured frame by frame from the reference.

Want a new style? Copy the `eclipse` folder, change the numbers. No code needed.

---

## Project map

```
backend/app/
  main.py            the API (upload, status, preview, download)
  jobs.py            runs each video job in the background
  media/             vertical UGC layout, audio, speech detection, person cut-out
  transcription/     speech → words (Apex), spelling fixes, timing cleanup
  captions/          features → roles → groups → hook placement → captions.json
renderer/            Remotion caption renderer + MP4 export
frontend/            the website
styles/eclipse/      the Eclipse look + fonts
samples/             demo input and output videos
```

---

## Results

Tested on the reference video:

- ✅ Roman Hinglish only, no Devanagari
- ✅ Word timings within about ±0.2 s of the original captions
- ✅ Picks the same hooks as the reference (**OBSIDIAN**, **PISCES**) without being told
- ✅ Hooks sit behind the speaker, in about the same size and position as the reference
- ⚡ 30 s of speech → captions in ~15 s on a laptop GPU

---

## Tech used (all free)

| Job | Tool |
| --- | --- |
| Speech to text | Whisper-Hindi2Hinglish-Apex |
| Finding speech | Silero VAD |
| Person cut-out | MediaPipe selfie segmenter |
| Video and audio | FFmpeg |
| Drawing captions | Remotion (free for individuals and small teams) |
| Backend | Python + FastAPI |
| Website | React + Vite |

**Going pro later?** Swap in a paid speech API (ElevenLabs, Sarvam, AssemblyAI), a sharper cut-out model (SAM 2.1), cloud rendering (Remotion Lambda) and cloud storage (S3). The rest of the project stays the same.
