"""
B-Roll Fetcher - Searches and downloads video clips from Pexels & Pixabay
based on scene keywords extracted from script analysis.
"""

import os
import requests
import random
import hashlib
from pathlib import Path


class BRollFetcher:
    def __init__(self):
        self.pexels_key = os.getenv("PEXELS_API_KEY")
        self.pixabay_key = os.getenv("PIXABAY_API_KEY")
        self.cache_dir = Path("static/uploads/broll_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()[:12]

    def search_pexels_video(self, query: str, duration: float = 5.0) -> dict | None:
        """Search Pexels for video clips matching the query."""
        if not self.pexels_key:
            return None

        headers = {"Authorization": self.pexels_key}
        params = {
            "query": query,
            "per_page": 5,
            "orientation": "landscape",
            "size": "medium"
        }

        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params=params,
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            videos = data.get("videos", [])
            if not videos:
                return None

            # Pick the best matching video
            for video in videos:
                files = video.get("video_files", [])
                # Prefer HD quality
                hd_files = [f for f in files if f.get("quality") in ["hd", "sd"] and f.get("width", 0) >= 640]
                if hd_files:
                    chosen = hd_files[0]
                    return {
                        "url": chosen["link"],
                        "width": chosen.get("width", 1280),
                        "height": chosen.get("height", 720),
                        "source": "pexels",
                        "id": video["id"],
                        "thumbnail": video.get("image", "")
                    }
        except Exception as e:
            print(f"[BRoll] Pexels error for '{query}': {e}")

        return None

    def search_pixabay_video(self, query: str) -> dict | None:
        """Search Pixabay for video clips."""
        if not self.pixabay_key:
            return None

        params = {
            "key": self.pixabay_key,
            "q": query,
            "video_type": "film",
            "per_page": 5,
            "safesearch": "true"
        }

        try:
            resp = requests.get(
                "https://pixabay.com/api/videos/",
                params=params,
                timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            hits = data.get("hits", [])
            if not hits:
                return None

            video = random.choice(hits[:3])
            videos_obj = video.get("videos", {})
            # Try medium or small quality
            for quality in ["medium", "small", "large"]:
                if quality in videos_obj:
                    v = videos_obj[quality]
                    return {
                        "url": v["url"],
                        "width": v.get("width", 1280),
                        "height": v.get("height", 720),
                        "source": "pixabay",
                        "id": video["id"],
                        "thumbnail": video.get("userImageURL", "")
                    }
        except Exception as e:
            print(f"[BRoll] Pixabay error for '{query}': {e}")

        return None

    def download_clip(self, video_info: dict, filename: str) -> str | None:
        """Download a video clip to local storage."""
        url = video_info["url"]
        filepath = self.cache_dir / filename

        if filepath.exists():
            return str(filepath)

        try:
            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            return str(filepath)
        except Exception as e:
            print(f"[BRoll] Download error: {e}")
            return None

    def fetch_for_scene(self, scene: dict) -> str | None:
        """
        Main method: search and download the best B-roll for a scene.
        Returns local file path or None.
        """
        keywords = scene.get("broll_keywords", [])
        scene_id = scene.get("id", 0)
        duration = scene.get("duration", 5.0)

        for query in keywords:
            cache_key = self._cache_key(query)
            cached_path = self.cache_dir / f"{cache_key}.mp4"

            if cached_path.exists():
                print(f"[BRoll] Cache hit for '{query}'")
                return str(cached_path)

            # Try Pexels first
            video_info = self.search_pexels_video(query, duration)

            # Fall back to Pixabay
            if not video_info:
                video_info = self.search_pixabay_video(query)

            if video_info:
                local_path = self.download_clip(video_info, f"{cache_key}.mp4")
                if local_path:
                    print(f"[BRoll] Downloaded '{query}' from {video_info['source']}")
                    return local_path

        print(f"[BRoll] No footage found for scene {scene_id}")
        return None

    def fetch_all_scenes(self, scenes: list, progress_callback=None) -> dict:
        """Fetch B-roll for all scenes. Returns {scene_id: local_path}."""
        results = {}
        total = len(scenes)

        for i, scene in enumerate(scenes):
            scene_id = scene["id"]
            clip_path = self.fetch_for_scene(scene)
            results[scene_id] = clip_path

            if progress_callback:
                progress_callback(
                    step="broll",
                    current=i + 1,
                    total=total,
                    message=f"Fetching B-roll {i+1}/{total}: {scene.get('broll_keywords', [''])[0]}"
                )

        return results
