"""
Multilingual Audio Transcriber — 100% Free using OpenAI Whisper (local)
Supports: English, Hindi, Nepali, + 90 other languages
Runs completely on your machine — no API key needed!
"""

import os
import json
import hashlib
import subprocess
from pathlib import Path


SUPPORTED_LANGUAGES = {
    "en": {"name": "English",  "native": "English",    "flag": "🇬🇧"},
    "hi": {"name": "Hindi",    "native": "हिन्दी",       "flag": "🇮🇳"},
    "ne": {"name": "Nepali",   "native": "नेपाली",       "flag": "🇳🇵"},
    "es": {"name": "Spanish",  "native": "Español",     "flag": "🇪🇸"},
    "fr": {"name": "French",   "native": "Français",    "flag": "🇫🇷"},
    "de": {"name": "German",   "native": "Deutsch",     "flag": "🇩🇪"},
    "ja": {"name": "Japanese", "native": "日本語",       "flag": "🇯🇵"},
    "zh": {"name": "Chinese",  "native": "中文",         "flag": "🇨🇳"},
    "ar": {"name": "Arabic",   "native": "العربية",     "flag": "🇸🇦"},
    "pt": {"name": "Portuguese","native": "Português",  "flag": "🇵🇹"},
    "ru": {"name": "Russian",  "native": "Русский",     "flag": "🇷🇺"},
    "ko": {"name": "Korean",   "native": "한국어",       "flag": "🇰🇷"},
    "it": {"name": "Italian",  "native": "Italiano",    "flag": "🇮🇹"},
    "ur": {"name": "Urdu",     "native": "اردو",        "flag": "🇵🇰"},
    "bn": {"name": "Bengali",  "native": "বাংলা",        "flag": "🇧🇩"},
}


class MultilingualTranscriber:
    def __init__(self, model_size: str = "base"):
        """
        model_size options:
          - tiny   : Fastest, least accurate (~1GB RAM)
          - base   : Good balance (~1GB RAM) ← Default
          - small  : Better quality (~2GB RAM)
          - medium : Best free quality (~5GB RAM)
          - large  : Most accurate (~10GB RAM)
        """
        self.model_size = model_size or os.getenv("WHISPER_MODEL", "base")
        self.model = None
        self.cache_dir = Path("static/uploads/transcript_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_model(self):
        """Lazy-load Whisper model (only when needed)."""
        if self.model is None:
            print(f"[Whisper] Loading {self.model_size} model... (first time only)")
            import whisper
            self.model = whisper.load_model(self.model_size)
            print(f"[Whisper] Model loaded!")
        return self.model

    def _cache_key(self, audio_path: str) -> str:
        """Generate cache key based on file content hash."""
        try:
            with open(audio_path, "rb") as f:
                content = f.read(1024 * 100)  # First 100KB
            return hashlib.md5(content).hexdigest()[:16] + f"_{self.model_size}"
        except Exception:
            return hashlib.md5(audio_path.encode()).hexdigest()[:16]

    def detect_language(self, audio_path: str) -> dict:
        """
        Auto-detect language from audio file.
        Returns: {"language": "en", "confidence": 0.95, "name": "English"}
        """
        try:
            model = self._load_model()
            import whisper
            audio = whisper.load_audio(audio_path)
            audio = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio).to(model.device)
            _, probs = model.detect_language(mel)
            detected = max(probs, key=probs.get)
            confidence = float(probs[detected])

            lang_info = SUPPORTED_LANGUAGES.get(detected, {
                "name": detected.upper(), "native": detected, "flag": "🌐"
            })

            return {
                "language": detected,
                "confidence": round(confidence, 3),
                "name": lang_info["name"],
                "native": lang_info.get("native", detected),
                "flag": lang_info.get("flag", "🌐"),
                "all_probs": {k: round(float(v), 4) for k, v in
                              sorted(probs.items(), key=lambda x: -x[1])[:5]}
            }
        except Exception as e:
            print(f"[Whisper] Language detection error: {e}")
            return {"language": "en", "confidence": 0.0, "name": "Unknown"}

    def transcribe(self, audio_path: str, language: str = None,
                   word_timestamps: bool = True) -> dict:
        """
        Transcribe audio file with optional word-level timestamps.
        Works for English, Hindi, Nepali and 90+ languages.

        Returns: {
          "text": str,
          "language": str,
          "language_name": str,
          "segments": [...],
          "words": [...],
          "duration": float
        }
        """
        cache_key = self._cache_key(audio_path)
        cache_path = self.cache_dir / f"{cache_key}.json"

        if cache_path.exists():
            print(f"[Whisper] Using cached transcript")
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

        try:
            model = self._load_model()
            print(f"[Whisper] Transcribing{' ('+language+')' if language else ''}...")

            result = model.transcribe(
                audio_path,
                language=language,
                word_timestamps=word_timestamps,
                verbose=False,
                task="transcribe"
            )

            # Extract word-level data
            all_words = []
            for seg in result.get("segments", []):
                for word in seg.get("words", []):
                    all_words.append({
                        "word": word.get("word", "").strip(),
                        "start": round(word.get("start", 0), 3),
                        "end": round(word.get("end", 0), 3),
                        "probability": round(word.get("probability", 0), 3)
                    })

            detected_lang = result.get("language", language or "en")
            lang_info = SUPPORTED_LANGUAGES.get(detected_lang, {
                "name": detected_lang.upper(), "flag": "🌐"
            })

            output = {
                "text": result.get("text", "").strip(),
                "language": detected_lang,
                "language_name": lang_info.get("name", detected_lang),
                "language_flag": lang_info.get("flag", "🌐"),
                "segments": [
                    {
                        "id": i,
                        "start": round(seg.get("start", 0), 3),
                        "end": round(seg.get("end", 0), 3),
                        "text": seg.get("text", "").strip()
                    }
                    for i, seg in enumerate(result.get("segments", []))
                ],
                "words": all_words,
                "duration": round(result["segments"][-1]["end"], 2) if result.get("segments") else 0,
                "word_count": len(result.get("text", "").split()),
            }

            # Cache the result
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            return output

        except Exception as e:
            print(f"[Whisper] Transcription error: {e}")
            return {
                "text": "",
                "language": "en",
                "language_name": "Unknown",
                "segments": [],
                "words": [],
                "duration": 0,
                "error": str(e)
            }

    def transcribe_and_translate(self, audio_path: str,
                                  source_lang: str = None) -> dict:
        """
        Transcribe audio AND translate to English simultaneously.
        Great for Hindi/Nepali audio → English captions.
        """
        cache_key = self._cache_key(audio_path) + "_translated"
        cache_path = self.cache_dir / f"{cache_key}.json"

        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

        try:
            model = self._load_model()

            # Original transcription
            original = self.transcribe(audio_path, language=source_lang)

            # Translation to English
            print(f"[Whisper] Translating to English...")
            translated = model.transcribe(
                audio_path,
                task="translate",
                language=source_lang,
                verbose=False
            )

            output = {
                **original,
                "translated_text": translated.get("text", "").strip(),
                "translated_segments": [
                    {
                        "id": i,
                        "start": round(seg.get("start", 0), 3),
                        "end": round(seg.get("end", 0), 3),
                        "text": seg.get("text", "").strip()
                    }
                    for i, seg in enumerate(translated.get("segments", []))
                ]
            }

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            return output

        except Exception as e:
            print(f"[Whisper] Translation error: {e}")
            return {"error": str(e), "text": "", "translated_text": ""}

    def generate_captions(self, transcript: dict,
                           words_per_line: int = 5,
                           style: str = "reels") -> list:
        """
        Generate caption segments from transcript.
        style: "reels" (short lines) | "standard" (longer) | "word" (word-by-word)
        """
        captions = []

        if style == "word":
            # Word-by-word (karaoke style)
            for word_data in transcript.get("words", []):
                captions.append({
                    "start": word_data["start"],
                    "end": word_data["end"],
                    "text": word_data["word"],
                    "words": [word_data["word"]]
                })
        elif style == "reels":
            # Group words into short chunks (reels style)
            words = transcript.get("words", [])
            for i in range(0, len(words), words_per_line):
                chunk = words[i:i + words_per_line]
                if chunk:
                    captions.append({
                        "start": chunk[0]["start"],
                        "end": chunk[-1]["end"],
                        "text": " ".join(w["word"] for w in chunk),
                        "words": [w["word"] for w in chunk]
                    })
        else:
            # Standard segment-based
            for seg in transcript.get("segments", []):
                captions.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"],
                    "words": seg["text"].split()
                })

        return captions

    def to_srt(self, captions: list) -> str:
        """Convert captions to SRT format."""
        lines = []
        for i, cap in enumerate(captions, 1):
            start = self._fmt_time(cap["start"])
            end = self._fmt_time(cap["end"])
            lines.append(f"{i}\n{start} --> {end}\n{cap['text']}\n")
        return "\n".join(lines)

    def _fmt_time(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
