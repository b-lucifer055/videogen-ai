"""
Music & SFX Fetcher - Finds background music and sound effects
from Pixabay Audio API and Freesound based on mood/genre.
"""

import os
import requests
import hashlib
import random
from pathlib import Path


class MusicFetcher:
    def __init__(self):
        self.pixabay_key = os.getenv("PIXABAY_API_KEY")
        self.freesound_key = os.getenv("FREESOUND_API_KEY")
        self.cache_dir = Path("static/uploads/music_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()[:12]

    # ── Mood → Music Mapping ────────────────────────────────────────────────
    MOOD_MUSIC_MAP = {
        "energetic": ["upbeat electronic", "energetic pop", "high energy dance"],
        "calm": ["ambient relaxing", "calm piano", "peaceful meditation"],
        "dramatic": ["cinematic epic", "dramatic orchestral", "tense thriller"],
        "funny": ["fun comedy", "quirky upbeat", "playful cartoon"],
        "inspirational": ["motivational uplifting", "inspiring piano", "positive corporate"],
        "sad": ["emotional sad piano", "melancholic ambient", "sad violin"],
        "happy": ["happy upbeat", "cheerful acoustic", "bright pop"],
        "tense": ["suspense thriller", "dark tense", "action intense"],
        "romantic": ["romantic love", "soft acoustic guitar", "gentle piano"],
        "corporate": ["corporate background", "professional business", "modern corporate"],
        "neutral": ["background music", "ambient neutral", "soft background"]
    }

    SFX_MOOD_MAP = {
        "whoosh": "whoosh transition",
        "fade": "soft transition",
        "energetic": "impact hit",
        "dramatic": "dramatic hit",
        "funny": "comedy boing",
        "keyboard typing": "keyboard typing",
        "crowd cheering": "crowd cheering applause",
        "nature": "nature birds ambient",
        "city": "city urban ambient",
        "notification": "notification ding",
        "explosion": "explosion boom",
        "heartbeat": "heartbeat pulse",
        "success": "success achievement",
        "error": "error buzz"
    }

    def search_pixabay_music(self, query: str) -> dict | None:
        """Search Pixabay for music tracks."""
        if not self.pixabay_key:
            return None
        params = {
            "key": self.pixabay_key,
            "q": query,
            "per_page": 5
        }
        try:
            resp = requests.get(
                "https://pixabay.com/api/music/",
                params=params,
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", [])
                if hits:
                    track = random.choice(hits[:3])
                    return {
                        "url": track.get("audio", ""),
                        "title": track.get("tags", query),
                        "duration": track.get("duration", 60),
                        "source": "pixabay"
                    }
        except Exception as e:
            print(f"[Music] Pixabay error: {e}")
        return None

    def search_freesound_sfx(self, query: str) -> dict | None:
        """Search Freesound for sound effects."""
        if not self.freesound_key:
            return None
        params = {
            "query": query,
            "token": self.freesound_key,
            "format": "json",
            "fields": "id,name,previews,duration",
            "filter": "duration:[0.1 TO 10]",
            "sort": "score"
        }
        try:
            resp = requests.get(
                "https://freesound.org/apiv2/search/text/",
                params=params,
                timeout=15
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    sfx = results[0]
                    previews = sfx.get("previews", {})
                    url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
                    return {
                        "url": url,
                        "title": sfx.get("name", query),
                        "duration": sfx.get("duration", 1.0),
                        "source": "freesound"
                    }
        except Exception as e:
            print(f"[SFX] Freesound error: {e}")
        return None

    def download_audio(self, url: str, filename: str) -> str | None:
        """Download audio file to cache."""
        if not url:
            return None
        filepath = self.cache_dir / filename
        if filepath.exists():
            return str(filepath)
        try:
            resp = requests.get(url, stream=True, timeout=30)
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=4096):
                    f.write(chunk)
            return str(filepath)
        except Exception as e:
            print(f"[Audio] Download error: {e}")
            return None

    def get_background_music(self, mood: str, genre: str = None) -> str | None:
        """Get background music track for a given mood."""
        queries = self.MOOD_MUSIC_MAP.get(mood.lower(), ["background music"])
        if genre:
            queries = [f"{genre} {q}" for q in queries[:2]] + queries

        for query in queries:
            cache_key = self._cache_key(query)
            cached = self.cache_dir / f"music_{cache_key}.mp3"
            if cached.exists():
                return str(cached)

            track = self.search_pixabay_music(query)
            if track and track["url"]:
                path = self.download_audio(track["url"], f"music_{cache_key}.mp3")
                if path:
                    return path

        return None

    def get_sfx(self, sfx_description: str) -> str | None:
        """Get sound effect for a given description."""
        if not sfx_description:
            return None

        # Map to better search query
        query = self.SFX_MOOD_MAP.get(sfx_description.lower(), sfx_description)
        cache_key = self._cache_key(query)
        cached = self.cache_dir / f"sfx_{cache_key}.mp3"

        if cached.exists():
            return str(cached)

        sfx = self.search_freesound_sfx(query)
        if sfx and sfx["url"]:
            path = self.download_audio(sfx["url"], f"sfx_{cache_key}.mp3")
            if path:
                return path

        return None

    def get_all_sfx_for_scenes(self, scenes: list, progress_callback=None) -> dict:
        """Get SFX for all scenes that need it."""
        results = {}
        sfx_scenes = [s for s in scenes if s.get("sfx")]

        for i, scene in enumerate(sfx_scenes):
            scene_id = scene["id"]
            sfx_path = self.get_sfx(scene["sfx"])
            results[scene_id] = sfx_path

            if progress_callback:
                progress_callback(
                    step="sfx",
                    current=i + 1,
                    total=len(sfx_scenes),
                    message=f"Fetching SFX: {scene.get('sfx', '')}"
                )

        return results
