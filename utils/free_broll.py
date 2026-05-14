"""
Free B-Roll Fetcher — Pexels + Pixabay (both 100% free)
No paid APIs needed!
"""

import os
import requests
import hashlib
import random
from pathlib import Path


class FreeBRollFetcher:
    def __init__(self):
        self.pexels_key = os.getenv("PEXELS_API_KEY", "")
        self.pixabay_key = os.getenv("PIXABAY_API_KEY", "")
        self.cache_dir = Path("static/uploads/broll_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, query: str) -> str:
        return hashlib.md5(query.lower().encode()).hexdigest()[:14]

    def search_pexels(self, query: str, orientation: str = "landscape") -> dict | None:
        if not self.pexels_key:
            return None
        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": self.pexels_key},
                params={"query": query, "per_page": 8, "orientation": orientation, "size": "medium"},
                timeout=15
            )
            if resp.status_code == 200:
                videos = resp.json().get("videos", [])
                for video in random.sample(videos, min(3, len(videos))):
                    files = video.get("video_files", [])
                    for f in sorted(files, key=lambda x: x.get("width", 0), reverse=True):
                        if f.get("width", 0) >= 640:
                            return {"url": f["link"], "source": "pexels",
                                    "width": f.get("width"), "height": f.get("height")}
        except Exception as e:
            print(f"[BRoll] Pexels error: {e}")
        return None

    def search_pixabay(self, query: str) -> dict | None:
        if not self.pixabay_key:
            return None
        try:
            resp = requests.get(
                "https://pixabay.com/api/videos/",
                params={"key": self.pixabay_key, "q": query, "per_page": 8,
                        "video_type": "film", "safesearch": "true"},
                timeout=15
            )
            if resp.status_code == 200:
                hits = resp.json().get("hits", [])
                if hits:
                    hit = random.choice(hits[:4])
                    videos = hit.get("videos", {})
                    for q in ["medium", "small", "large"]:
                        if q in videos:
                            v = videos[q]
                            return {"url": v["url"], "source": "pixabay",
                                    "width": v.get("width"), "height": v.get("height")}
        except Exception as e:
            print(f"[BRoll] Pixabay error: {e}")
        return None

    def download(self, url: str, filename: str) -> str | None:
        filepath = self.cache_dir / filename
        if filepath.exists() and filepath.stat().st_size > 10000:
            return str(filepath)
        try:
            resp = requests.get(url, stream=True, timeout=60,
                                headers={"User-Agent": "VideoGen/1.0"})
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            return str(filepath) if filepath.stat().st_size > 10000 else None
        except Exception as e:
            print(f"[BRoll] Download error: {e}")
            if filepath.exists():
                filepath.unlink()
            return None

    def fetch(self, query: str, orientation: str = "landscape") -> str | None:
        """Fetch B-roll clip for a query. Returns local path."""
        cache_key = self._cache_key(query)
        cached = self.cache_dir / f"{cache_key}.mp4"
        if cached.exists() and cached.stat().st_size > 10000:
            return str(cached)

        # Try Pexels first
        result = self.search_pexels(query, orientation)
        if not result:
            result = self.search_pixabay(query)

        if result:
            path = self.download(result["url"], f"{cache_key}.mp4")
            if path:
                print(f"[BRoll] ✅ '{query}' from {result['source']}")
                return path

        print(f"[BRoll] ❌ No clip found for '{query}'")
        return None

    def fetch_all(self, scenes: list, orientation: str = "landscape",
                  progress_callback=None) -> dict:
        results = {}
        for i, scene in enumerate(scenes):
            sid = scene["id"]
            keywords = scene.get("broll_keywords", [])
            path = None
            for kw in keywords:
                path = self.fetch(kw, orientation)
                if path:
                    break
            results[sid] = path
            if progress_callback:
                progress_callback(step="broll", current=i+1, total=len(scenes),
                                  message=f"B-roll {i+1}/{len(scenes)}: {keywords[0] if keywords else '...'}")
        return results


class FreeMusicFetcher:
    def __init__(self):
        self.pixabay_key = os.getenv("PIXABAY_API_KEY", "")
        self.freesound_key = os.getenv("FREESOUND_API_KEY", "")
        self.cache_dir = Path("static/uploads/music_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, query: str) -> str:
        return hashlib.md5(query.lower().encode()).hexdigest()[:14]

    MOOD_QUERIES = {
        "energetic":     ["energetic upbeat electronic", "power anthems", "high energy music"],
        "calm":          ["calm ambient relaxing", "peaceful piano", "lo-fi chill"],
        "dramatic":      ["cinematic dramatic orchestra", "epic trailer", "dark suspense"],
        "funny":         ["comedy funny background", "quirky ukulele", "playful cartoon"],
        "inspirational": ["inspirational uplifting", "motivational background", "positive corporate"],
        "sad":           ["sad emotional piano", "melancholic ambient", "heartfelt strings"],
        "happy":         ["happy cheerful pop", "feel good upbeat", "bright acoustic"],
        "travel":        ["travel adventure music", "epic journey", "world exploration"],
        "nature":        ["nature acoustic ambient", "forest sounds music", "peaceful outdoor"],
        "business":      ["corporate professional background", "business presentation", "modern tech"],
        "fitness":       ["workout motivation music", "gym energy electronic", "training power"],
        "food":          ["cooking cafe jazz", "warm acoustic kitchen", "restaurant ambient"],
        "tech":          ["technology futuristic electronic", "digital innovation", "modern tech ambient"],
        "informative":   ["documentary background music", "educational ambient", "neutral background"],
        "default":       ["background music ambient", "neutral instrumental", "soft background"],
    }

    def search_pixabay_music(self, query: str) -> dict | None:
        if not self.pixabay_key:
            return None
        try:
            resp = requests.get(
                "https://pixabay.com/api/music/",
                params={"key": self.pixabay_key, "q": query, "per_page": 5},
                timeout=15
            )
            if resp.status_code == 200:
                hits = resp.json().get("hits", [])
                if hits:
                    track = random.choice(hits[:3])
                    return {"url": track.get("audio", ""), "title": track.get("tags", query),
                            "source": "pixabay"}
        except Exception as e:
            print(f"[Music] Pixabay error: {e}")
        return None

    def search_freesound_sfx(self, query: str) -> dict | None:
        if not self.freesound_key:
            return None
        try:
            resp = requests.get(
                "https://freesound.org/apiv2/search/text/",
                params={"query": query, "token": self.freesound_key, "format": "json",
                        "fields": "id,name,previews,duration",
                        "filter": "duration:[0.5 TO 8]", "sort": "score"},
                timeout=15
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    sfx = results[0]
                    previews = sfx.get("previews", {})
                    url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
                    return {"url": url, "title": sfx.get("name", query), "source": "freesound"}
        except Exception as e:
            print(f"[SFX] Freesound error: {e}")
        return None

    def download_audio(self, url: str, filename: str) -> str | None:
        if not url:
            return None
        filepath = self.cache_dir / filename
        if filepath.exists() and filepath.stat().st_size > 1000:
            return str(filepath)
        try:
            resp = requests.get(url, stream=True, timeout=30,
                                headers={"User-Agent": "VideoGen/1.0"})
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(4096):
                    f.write(chunk)
            return str(filepath) if filepath.stat().st_size > 1000 else None
        except Exception as e:
            print(f"[Audio] Download error: {e}")
            return None

    def get_music(self, mood: str) -> str | None:
        queries = self.MOOD_QUERIES.get(mood, self.MOOD_QUERIES["default"])
        for query in queries:
            cache_key = self._cache_key(query)
            cached = self.cache_dir / f"music_{cache_key}.mp3"
            if cached.exists() and cached.stat().st_size > 1000:
                return str(cached)
            track = self.search_pixabay_music(query)
            if track and track.get("url"):
                path = self.download_audio(track["url"], f"music_{cache_key}.mp3")
                if path:
                    return path
        return None

    def get_sfx(self, description: str) -> str | None:
        if not description:
            return None
        cache_key = self._cache_key(description)
        cached = self.cache_dir / f"sfx_{cache_key}.mp3"
        if cached.exists() and cached.stat().st_size > 1000:
            return str(cached)
        sfx = self.search_freesound_sfx(description)
        if sfx and sfx.get("url"):
            return self.download_audio(sfx["url"], f"sfx_{cache_key}.mp3")
        return None
