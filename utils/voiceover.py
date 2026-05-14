"""
Voiceover Generator - Converts script text to speech using
ElevenLabs, OpenAI TTS, or Google Cloud TTS.
"""

import os
import io
import hashlib
from pathlib import Path


class VoiceoverGenerator:
    def __init__(self):
        self.cache_dir = Path("static/uploads/tts_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")

    def _cache_key(self, text: str, voice: str, provider: str) -> str:
        content = f"{provider}:{voice}:{text}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    # ── ElevenLabs ──────────────────────────────────────────────────────────
    ELEVENLABS_VOICES = {
        "rachel": "21m00Tcm4TlvDq8ikWAM",
        "domi": "AZnzlk1XvdvUeBnXmlld",
        "bella": "EXAVITQu4vr4xnSDxMaL",
        "adam": "pNInz6obpgDQGcFmaJgB",
        "sam": "yoZ06aMxZJJ28mfd3POQ",
        "elli": "MF3mGyEYCl7XYWbV9V6O",
        "josh": "TxGEqnHWrfWFTfGW9XjX",
        "arnold": "VR6AewLTigWG4xSOukaG",
        "callum": "N2lVS1w4EtoT3dr4eOWO",
        "charlie": "IKne3meq5aSn9XLyUdCD"
    }

    def generate_elevenlabs(self, text: str, voice_id: str, stability: float = 0.5,
                             similarity_boost: float = 0.75, style: float = 0.0,
                             speed: float = 1.0) -> bytes | None:
        """Generate audio using ElevenLabs API."""
        try:
            import requests
            headers = {
                "xi-api-key": self.elevenlabs_key,
                "Content-Type": "application/json"
            }
            payload = {
                "text": text,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity_boost,
                    "style": style,
                    "use_speaker_boost": True
                }
            }
            resp = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                json=payload,
                headers=headers,
                timeout=30
            )
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            print(f"[TTS] ElevenLabs error: {e}")
            return None

    # ── OpenAI TTS ──────────────────────────────────────────────────────────
    OPENAI_VOICES = {
        "alloy": "alloy",
        "echo": "echo",
        "fable": "fable",
        "onyx": "onyx",
        "nova": "nova",
        "shimmer": "shimmer"
    }

    def generate_openai_tts(self, text: str, voice: str = "nova",
                             speed: float = 1.0) -> bytes | None:
        """Generate audio using OpenAI TTS."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_key)
            response = client.audio.speech.create(
                model="tts-1-hd",
                voice=voice,
                input=text,
                speed=speed,
                response_format="mp3"
            )
            return response.content
        except Exception as e:
            print(f"[TTS] OpenAI TTS error: {e}")
            return None

    # ── Google Cloud TTS ────────────────────────────────────────────────────
    GOOGLE_VOICES = {
        "en-US-Neural2-A": {"language": "en-US", "gender": "MALE"},
        "en-US-Neural2-C": {"language": "en-US", "gender": "FEMALE"},
        "en-US-Neural2-D": {"language": "en-US", "gender": "MALE"},
        "en-US-Neural2-F": {"language": "en-US", "gender": "FEMALE"},
        "en-US-Wavenet-A": {"language": "en-US", "gender": "MALE"},
        "en-US-Wavenet-C": {"language": "en-US", "gender": "FEMALE"},
    }

    def generate_google_tts(self, text: str, voice_name: str = "en-US-Neural2-C",
                             speaking_rate: float = 1.0, pitch: float = 0.0) -> bytes | None:
        """Generate audio using Google Cloud TTS."""
        try:
            from google.cloud import texttospeech
            client = texttospeech.TextToSpeechClient()
            voice_info = self.GOOGLE_VOICES.get(voice_name, {"language": "en-US", "gender": "NEUTRAL"})

            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=voice_info["language"],
                name=voice_name,
                ssml_gender=texttospeech.SsmlVoiceGender[voice_info["gender"]]
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=speaking_rate,
                pitch=pitch
            )
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            return response.audio_content
        except Exception as e:
            print(f"[TTS] Google TTS error: {e}")
            return None

    # ── Main Method ─────────────────────────────────────────────────────────
    def generate(self, text: str, config: dict) -> str | None:
        """
        Generate voiceover for given text with config.
        config: {
          provider: "elevenlabs" | "openai" | "google",
          voice: str,
          speed: float,
          stability: float,   # ElevenLabs only
          similarity: float,  # ElevenLabs only
          pitch: float,       # Google only
        }
        Returns: local file path to .mp3
        """
        provider = config.get("provider", "openai")
        voice = config.get("voice", "nova")
        speed = config.get("speed", 1.0)

        cache_key = self._cache_key(text, voice, provider)
        cache_path = self.cache_dir / f"{cache_key}.mp3"

        if cache_path.exists():
            return str(cache_path)

        audio_bytes = None

        if provider == "elevenlabs" and self.elevenlabs_key:
            voice_id = self.ELEVENLABS_VOICES.get(voice, voice)
            audio_bytes = self.generate_elevenlabs(
                text, voice_id,
                stability=config.get("stability", 0.5),
                similarity_boost=config.get("similarity", 0.75),
                speed=speed
            )

        elif provider == "openai" and self.openai_key:
            audio_bytes = self.generate_openai_tts(text, voice=voice, speed=speed)

        elif provider == "google":
            audio_bytes = self.generate_google_tts(
                text, voice_name=voice,
                speaking_rate=speed,
                pitch=config.get("pitch", 0.0)
            )

        if audio_bytes:
            with open(cache_path, "wb") as f:
                f.write(audio_bytes)
            return str(cache_path)

        return None

    def generate_full_script(self, script: str, config: dict,
                              progress_callback=None) -> str | None:
        """Generate voiceover for the entire script at once."""
        if progress_callback:
            progress_callback(step="voiceover", current=0, total=1,
                              message="Generating voiceover...")
        result = self.generate(script, config)
        if progress_callback:
            progress_callback(step="voiceover", current=1, total=1,
                              message="Voiceover complete!")
        return result

    def get_available_voices(self) -> dict:
        """Return all available voices by provider."""
        return {
            "elevenlabs": list(self.ELEVENLABS_VOICES.keys()),
            "openai": list(self.OPENAI_VOICES.keys()),
            "google": list(self.GOOGLE_VOICES.keys())
        }
