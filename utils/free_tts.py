"""
Free TTS Engine — No API keys needed!
Supports: edge-tts (best), gTTS (simple), pyttsx3 (offline)
"""

import os
import asyncio
import hashlib
import tempfile
from pathlib import Path


class FreeTTS:
    def __init__(self):
        self.cache_dir = Path("static/uploads/tts_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── All Available Voices ─────────────────────────────────────────────────
    EDGE_VOICES = {
        # English
        "en-US-AriaNeural":    {"lang": "en", "gender": "F", "style": "Natural"},
        "en-US-GuyNeural":     {"lang": "en", "gender": "M", "style": "Natural"},
        "en-US-JennyNeural":   {"lang": "en", "gender": "F", "style": "Friendly"},
        "en-US-EricNeural":    {"lang": "en", "gender": "M", "style": "Calm"},
        "en-US-SaraNeural":    {"lang": "en", "gender": "F", "style": "Cheerful"},
        "en-US-TonyNeural":    {"lang": "en", "gender": "M", "style": "Energetic"},
        "en-GB-SoniaNeural":   {"lang": "en", "gender": "F", "style": "British"},
        "en-GB-RyanNeural":    {"lang": "en", "gender": "M", "style": "British"},
        "en-AU-NatashaNeural": {"lang": "en", "gender": "F", "style": "Australian"},
        # Hindi
        "hi-IN-SwaraNeural":   {"lang": "hi", "gender": "F", "style": "Natural"},
        "hi-IN-MadhurNeural":  {"lang": "hi", "gender": "M", "style": "Natural"},
        # Nepali
        "ne-NP-HemkalaNeural": {"lang": "ne", "gender": "F", "style": "Natural"},
        "ne-NP-SagarNeural":   {"lang": "ne", "gender": "M", "style": "Natural"},
    }

    GTTS_LANGS = {
        "English":  "en",
        "Hindi":    "hi",
        "Nepali":   "ne",
        "Spanish":  "es",
        "French":   "fr",
        "German":   "de",
        "Japanese": "ja",
    }

    def _cache_key(self, text: str, voice: str, provider: str, speed: float) -> str:
        content = f"{provider}:{voice}:{speed}:{text[:100]}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    # ── Edge TTS (Microsoft — Best free quality) ─────────────────────────────
    async def _edge_tts_async(self, text: str, voice: str, rate: str, output_path: str):
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(output_path)
            return True
        except Exception as e:
            print(f"[TTS-Edge] Error: {e}")
            return False

    def generate_edge_tts(self, text: str, voice: str = "en-US-AriaNeural",
                           speed: float = 1.0) -> str | None:
        """Generate speech with Microsoft Edge TTS (completely free)."""
        cache_key = self._cache_key(text, voice, "edge", speed)
        cache_path = self.cache_dir / f"{cache_key}.mp3"

        if cache_path.exists():
            return str(cache_path)

        # Convert speed to edge-tts rate format (+10% = "+10%")
        rate_pct = int((speed - 1.0) * 100)
        rate_str = f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%"

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(
                self._edge_tts_async(text, voice, rate_str, str(cache_path))
            )
            loop.close()

            if success and cache_path.exists():
                return str(cache_path)
        except Exception as e:
            print(f"[TTS-Edge] Async error: {e}")

        return None

    # ── gTTS (Google — Simple free) ──────────────────────────────────────────
    def generate_gtts(self, text: str, lang: str = "en",
                      slow: bool = False) -> str | None:
        """Generate speech with Google Text-to-Speech (free)."""
        cache_key = self._cache_key(text, lang, "gtts", 1.0)
        cache_path = self.cache_dir / f"{cache_key}.mp3"

        if cache_path.exists():
            return str(cache_path)

        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang=lang, slow=slow)
            tts.save(str(cache_path))
            return str(cache_path)
        except Exception as e:
            print(f"[TTS-gTTS] Error: {e}")
            return None

    # ── pyttsx3 (Offline — No internet needed) ───────────────────────────────
    def generate_pyttsx3(self, text: str, rate: int = 200,
                          volume: float = 1.0) -> str | None:
        """Generate speech offline with pyttsx3."""
        cache_key = self._cache_key(text, "pyttsx3", "local", rate / 200)
        cache_path = self.cache_dir / f"{cache_key}.mp3"

        if cache_path.exists():
            return str(cache_path)

        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", rate)
            engine.setProperty("volume", volume)

            wav_path = str(cache_path).replace(".mp3", ".wav")
            engine.save_to_file(text, wav_path)
            engine.runAndWait()

            # Convert WAV to MP3
            if Path(wav_path).exists():
                from pydub import AudioSegment
                audio = AudioSegment.from_wav(wav_path)
                audio.export(str(cache_path), format="mp3")
                Path(wav_path).unlink()
                return str(cache_path)
        except Exception as e:
            print(f"[TTS-pyttsx3] Error: {e}")

        return None

    # ── Main Generate Method ─────────────────────────────────────────────────
    def generate(self, text: str, config: dict) -> str | None:
        """
        Generate speech with the specified free TTS provider.
        config: {
          provider: "edge_tts" | "gtts" | "pyttsx3",
          voice: str,
          speed: float,
          lang: str  (for gtts)
        }
        """
        provider = config.get("provider", "edge_tts")
        voice = config.get("voice", "en-US-AriaNeural")
        speed = float(config.get("speed", 1.0))

        if provider == "edge_tts":
            return self.generate_edge_tts(text, voice, speed)
        elif provider == "gtts":
            lang = config.get("lang", "en")
            return self.generate_gtts(text, lang)
        elif provider == "pyttsx3":
            rate = int(150 * speed)
            return self.generate_pyttsx3(text, rate)

        # Auto-fallback chain
        result = self.generate_edge_tts(text, voice, speed)
        if not result:
            result = self.generate_gtts(text, config.get("lang", "en"))
        if not result:
            result = self.generate_pyttsx3(text)
        return result

    def get_all_voices(self) -> dict:
        return {
            "edge_tts": {
                k: v for k, v in self.EDGE_VOICES.items()
            },
            "gtts": self.GTTS_LANGS,
            "pyttsx3": {"system_default": {"lang": "any", "gender": "varies", "style": "Offline"}}
        }
