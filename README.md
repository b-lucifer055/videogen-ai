# 🎬 VideoGen AI — Script-to-Video Platform

> Upload a script → Get a full-length, production-ready video automatically.

VideoGen is a full-stack AI video creation platform that converts your script into a polished, download-ready video complete with B-roll footage, AI voiceover, background music, sound effects, captions, and seamless transitions.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **AI Script Analysis** | GPT-4 breaks your script into scenes, detects mood, extracts B-roll keywords |
| 🎬 **B-Roll Auto-Fetch** | Searches Pexels + Pixabay for relevant video clips per scene |
| 🎤 **AI Voiceover** | ElevenLabs / OpenAI TTS / Google Cloud TTS with 15+ voices |
| 📝 **Auto Captions** | Whisper-powered captions with reels-style formatting |
| 🎵 **Music & SFX** | Mood-matched background music (Pixabay) + sound effects (Freesound) |
| ✨ **Transitions** | Fade, dissolve, wipe, zoom — matched to scene mood |
| 📐 **Multi-Format** | YouTube 16:9, TikTok/Reels 9:16, Instagram 1:1, and more |
| ⬇️ **Download Ready** | High-quality MP4 output, ready to upload anywhere |
| 📊 **Dashboard** | Track all jobs, monitor progress in real-time via WebSocket |

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11 + Flask + Flask-SocketIO |
| Video Engine | ffmpeg + MoviePy |
| AI — Script | OpenAI GPT-4o |
| AI — TTS | ElevenLabs / OpenAI TTS-1-HD / Google Cloud TTS |
| AI — Captions | OpenAI Whisper |
| B-Roll | Pexels API + Pixabay API |
| Music | Pixabay Audio API |
| SFX | Freesound API |
| Real-time | Socket.IO (WebSocket) |
| Deploy | Docker / Railway / Heroku |

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone <your-repo>
cd videogen
cp .env.example .env
```

### 2. Fill in `.env`

```env
OPENAI_API_KEY=sk-...          # Required
PEXELS_API_KEY=...             # Free — pexels.com/api
PIXABAY_API_KEY=...            # Free — pixabay.com/api/docs
ELEVENLABS_API_KEY=...         # Optional premium TTS
FREESOUND_API_KEY=...          # Free — freesound.org/apiv2/apply
```

### 3. Install & Run (Local)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install ffmpeg (required!)
# macOS:   brew install ffmpeg
# Ubuntu:  sudo apt install ffmpeg
# Windows: https://ffmpeg.org/download.html

# Start the server
python app.py
```

Open: **http://localhost:5000**

### 4. Run with Docker

```bash
docker-compose up --build
```

---

## ☁️ Cloud Deployment

### Railway (Recommended)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Deploy
railway login
railway init
railway up
```

Set environment variables in the Railway dashboard.

### Heroku

```bash
heroku create your-videogen-app
heroku stack:set container
git push heroku main
heroku config:set OPENAI_API_KEY=sk-...
```

### Any Docker Host

```bash
docker build -t videogen .
docker run -p 5000:5000 \
  -e OPENAI_API_KEY=sk-... \
  -e PEXELS_API_KEY=... \
  -v ./outputs:/app/static/outputs \
  videogen
```

---

## 📐 Supported Output Formats

| Format | Dimensions | Best For |
|--------|-----------|----------|
| Portrait 9:16 (1080p) | 1080×1920 | TikTok, Instagram Reels, YouTube Shorts |
| Landscape 16:9 (1080p) | 1920×1080 | YouTube, Facebook |
| Square 1:1 (1080p) | 1080×1080 | Instagram Posts |
| Landscape 720p | 1280×720 | General use |
| Portrait 720p | 720×1280 | Stories |
| Twitter/X | 1280×720 | Twitter/X Video |

---

## 🎤 Voice Providers

### OpenAI TTS (Default)
- Voices: alloy, echo, fable, onyx, nova, shimmer
- Speed: 0.5x–2.0x
- Model: tts-1-hd

### ElevenLabs (Premium)
- 10+ natural voices (Rachel, Adam, Josh, etc.)
- Stability & Similarity controls
- Most realistic output

### Google Cloud TTS
- Neural2 & WaveNet voices
- Custom pitch & speed
- Requires service account JSON

---

## 🔌 API Keys Setup

| Service | URL | Cost |
|---------|-----|------|
| OpenAI | https://platform.openai.com/api-keys | Pay-per-use (~$0.01-0.10/video) |
| ElevenLabs | https://elevenlabs.io/app/settings/api-keys | Free 10k chars/mo |
| Pexels | https://www.pexels.com/api/ | 100% Free |
| Pixabay | https://pixabay.com/api/docs/ | 100% Free |
| Freesound | https://freesound.org/apiv2/apply | 100% Free |

---

## 📁 Project Structure

```
videogen/
├── app.py                      # Flask application
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── railway.json
├── Procfile
│
├── utils/
│   ├── script_analyzer.py      # GPT-4 script → scenes
│   ├── broll_fetcher.py        # Pexels + Pixabay search
│   ├── voiceover.py            # ElevenLabs / OpenAI / Google TTS
│   ├── music_fetcher.py        # Pixabay Music + Freesound SFX
│   ├── caption_generator.py    # Whisper + SRT/ASS generation
│   ├── video_composer.py       # ffmpeg video assembly engine
│   ├── pipeline.py             # Full orchestration pipeline
│   └── job_manager.py          # Job queue + status tracking
│
├── templates/
│   ├── base.html               # Navigation + shared styles
│   ├── index.html              # Studio (main page)
│   ├── dashboard.html          # Job tracking + downloads
│   └── settings.html           # API config + system status
│
└── static/
    ├── outputs/                # Generated videos
    └── uploads/
        ├── broll_cache/        # Cached B-roll clips
        ├── tts_cache/          # Cached TTS audio
        ├── music_cache/        # Cached music/SFX
        └── temp/               # Temp composition files
```

---

## 🛠️ How It Works

```
Script Input
     │
     ▼
1. 🧠 GPT-4 Analysis
   - Splits into scenes
   - Detects mood, theme
   - Extracts B-roll keywords
   - Suggests music genre, transitions
     │
     ▼
2. 🎬 B-Roll Fetching (Pexels/Pixabay)
   - Searches per-scene keywords
   - Downloads & caches clips
     │
     ├──▶ 3. 🎤 Voiceover Generation (ElevenLabs/OpenAI/Google)
     │        Full script → MP3 audio
     │
     ├──▶ 4. 🎵 Music & SFX (Pixabay/Freesound)
     │        Mood-matched BGM + per-scene SFX
     │
     └──▶ 5. 📝 Caption Generation (Whisper/Script)
              Word-level timestamps → SRT
                │
                ▼
         6. 🎞️ Video Composition (ffmpeg)
            - Resize/crop B-roll per scene
            - Apply transitions (fade/dissolve/wipe)
            - Concat all scenes
            - Mix audio (voice + music)
            - Burn captions
            - Export for each size format
                │
                ▼
         7. ⬇️ Download Ready MP4
```

---

## ⚡ Performance Notes

- A 1-2 minute script takes ~2-8 minutes to process
- B-roll download is the bottleneck (cached after first run)
- Use `draft` quality for faster previews
- All B-roll + TTS is cached locally for reuse

---

## 📝 License

MIT License — free to use and modify.
