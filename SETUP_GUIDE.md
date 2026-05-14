# 🎬 VideoGen AI — FREE Edition Setup Guide

## What's New in This Version
- ✅ **100% Free** — No paid APIs whatsoever
- 🎬 **Raw Clips Editor** — Upload footage → auto-edit into reels
- 🎙️ **Audio → Video** — Upload audio → full video (Hindi/Nepali/English support)
- 🌐 **Multilingual** — Whisper recognizes 90+ languages

---

## ⚡ Quick Start (5 minutes)

### Step 1 — Install Python
Download from **python.org/downloads** — check ✅ "Add to PATH"

### Step 2 — Install ffmpeg

**Windows:**
1. Download from: https://www.gyan.dev/ffmpeg/builds/ → `ffmpeg-release-essentials.zip`
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to System PATH
4. Restart terminal → test: `ffmpeg -version`

**Mac:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg -y
```

### Step 3 — Setup Project

```bash
cd videogen
cp .env.example .env
```

Edit `.env` — minimum required (all free!):
```env
SECRET_KEY=any-random-text-here
PEXELS_API_KEY=your-free-pexels-key
PIXABAY_API_KEY=your-free-pixabay-key
```

Get free keys:
- Pexels: https://www.pexels.com/api/
- Pixabay: https://pixabay.com/api/docs/
- Freesound: https://freesound.org/apiv2/apply/

### Step 4 — Install & Run

```bash
# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open: **http://localhost:5000**

---

## 📌 First-Time Notes

- **Whisper downloads ~140MB** on first audio transcription (one-time only)
- **B-roll clips are cached** — second run is much faster for similar topics
- **TTS audio is cached** — same text won't re-generate
- Processing time: ~2-5 min for a 1-2 minute video

---

## 🎬 Three Modes

### 1. Script Studio (/)
- Paste your script → AI creates full video
- Voiceover: edge-tts (300+ voices, Hindi/Nepali/English)
- B-Roll: Pexels + Pixabay (free)
- Music: Pixabay Audio (free)
- Captions: Whisper-based (free)

### 2. Raw Clips Editor (/clips)
- Upload your own video clips
- Auto Mode: AI edits everything
- Manual Mode: You control each clip
- Color grading: 10+ presets
- Custom audio: Upload your own track

### 3. Audio → Video (/audio)
- Upload any audio (MP3/WAV/M4A/etc.)
- Auto-detects language (English/Hindi/Nepali/90+ more)
- Transcribes with Whisper (100% local, free)
- Fetches matching B-roll footage
- Adds synced captions (reels/standard/word-by-word)
- Optional: translate captions to English

---

## 🛑 Troubleshooting

| Problem | Fix |
|---------|-----|
| `edge-tts` fails | Check internet connection (needs internet for TTS) |
| Whisper is slow | Use `tiny` or `base` model in `.env` |
| No B-roll found | Add Pexels/Pixabay API keys |
| ffmpeg not found | Re-add to PATH and restart terminal |
| `ModuleNotFoundError` | Make sure venv is active |
| Port in use | Change `PORT=5001` in `.env` |
