# Glido Labs Assignment

## CapSync — Hinglish Caption Engine

CapSync puts **animated captions** on your videos, automatically.

You upload a video → it listens to the speech → writes the words in **Roman Hinglish** (like *"bhai ye bahut accha hai"*) → shows a live preview in the **Eclipse** caption style → you download the finished MP4.

It works with **English, Hindi and Hinglish** (Hindi + English mixed), and everything runs **free on your own computer**.

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

> The first start downloads the speech model (~1.6 GB) once. Wait until the terminal is quiet, then upload a video.

### 6. Use it

1. Drop a video (MP4, MOV, WebM or MKV).
2. Click **Generate captions** and wait a few seconds.
3. Watch the **preview**.
4. Click **Export MP4**, then **Download**.

Want to test quickly? Try `samples/demo_input.mp4`.

---

## How it works (the simple version)

```
Video → get the audio → AI writes the words + timings → pick groups, highlights and hooks → draw captions → MP4
```

The project has **4 parts**, and each one does one job:

| Part | Folder | What it does |
| --- | --- | --- |
| 🎧 **Listener** | `backend/app/transcription` | Turns speech into words with exact timings |
| 🧠 **Caption brain** | `backend/app/captions` | Decides how words are grouped, which word is highlighted, and which words become big "hooks" |
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
| **Hook** | a huge word at the top of the screen (like **OBSIDIAN**) |

Captions are split at natural **pauses**, at the end of sentences, or when they get too wide for the screen.

### 🎨 Renderer — drawing the captions

Built with **[Remotion](https://www.remotion.dev/)** (React for videos).

- The **same code** draws the live preview and the final MP4, so what you see is what you get.
- When exporting, it draws **only the captions**, and **FFmpeg** puts them on top of your video. That's what makes export fast.

### 🎨 The Eclipse style

All the looks live in one file: **`styles/eclipse/style.json`**. It was copied frame by frame from the reference video:

- Bold white captions near the bottom, the spoken word turns **yellow**.
- Hooks appear **yellow on a soft yellow box** for about half a second, then turn **white**.
- Fonts: **Montserrat** and **Anton** (both free, included).

Want a new style? Copy the `eclipse` folder, change the numbers. No code needed.

---

## Project map

```
backend/app/
  main.py            the API (upload, status, export, download)
  jobs.py            runs each video job in the background
  media/             reads videos, extracts audio, finds speech
  transcription/     speech → words (Apex), spelling fixes, timing cleanup
  captions/          features → roles → groups → captions.json
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
- ⚡ 30 s of speech → captions in ~15 s on a laptop GPU
- ⚡ 8 s video → MP4 in ~16 s

---

## Tech used (all free)

| Job | Tool |
| --- | --- |
| Speech to text | Whisper-Hindi2Hinglish-Apex |
| Finding speech | Silero VAD |
| Video and audio | FFmpeg |
| Drawing captions | Remotion (free for individuals and small teams) |
| Backend | Python + FastAPI |
| Website | React + Vite |

**Going pro later?** Swap in a paid speech API (ElevenLabs, Sarvam, AssemblyAI), cloud rendering (Remotion Lambda) and cloud storage (S3). The rest of the project stays the same.
