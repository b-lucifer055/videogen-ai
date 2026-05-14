"""
Free Script Analyzer — No paid APIs!
Uses local NLP + keyword extraction + heuristics instead of GPT-4.
"""

import re
import json
import hashlib
from pathlib import Path


# ── Mood Detection Keywords ───────────────────────────────────────────────────
MOOD_KEYWORDS = {
    "energetic":     ["amazing", "incredible", "exciting", "fast", "quick", "powerful", "epic", "awesome", "explosive", "dynamic", "rush", "thrilling"],
    "calm":          ["peaceful", "serene", "gentle", "soft", "quiet", "relaxing", "meditative", "tranquil", "slow", "breath", "zen"],
    "dramatic":      ["danger", "crisis", "dark", "intense", "shocking", "reveal", "twist", "secret", "mystery", "terrifying", "haunting"],
    "funny":         ["funny", "hilarious", "laugh", "joke", "comedy", "weird", "awkward", "silly", "absurd", "ridiculous", "crazy"],
    "inspirational": ["inspire", "motivate", "dream", "achieve", "success", "goal", "overcome", "believe", "transform", "journey", "purpose", "courage", "potential"],
    "sad":           ["miss", "loss", "grief", "sad", "cry", "tears", "heartbreak", "lonely", "pain", "suffer", "regret", "goodbye"],
    "happy":         ["happy", "joy", "celebrate", "love", "wonderful", "beautiful", "smile", "bright", "sunshine", "fun", "delight", "cheer"],
    "informative":   ["learn", "discover", "fact", "science", "research", "study", "explain", "understand", "knowledge", "data", "analysis", "history"],
    "travel":        ["travel", "destination", "explore", "adventure", "world", "country", "visit", "trip", "journey", "landscape", "culture"],
    "business":      ["business", "company", "market", "strategy", "profit", "growth", "entrepreneur", "startup", "investment", "revenue"],
    "nature":        ["nature", "forest", "mountain", "ocean", "wildlife", "animal", "plant", "earth", "environment", "ecosystem"],
    "food":          ["food", "recipe", "cook", "eat", "delicious", "restaurant", "chef", "meal", "ingredient", "flavor", "taste"],
    "fitness":       ["workout", "exercise", "fitness", "gym", "health", "body", "training", "muscle", "strength", "cardio"],
    "tech":          ["technology", "app", "software", "code", "digital", "AI", "computer", "device", "internet", "innovation"],
}

MUSIC_MOOD_MAP = {
    "energetic":     {"genre": "Electronic / EDM", "tempo": "fast", "tracks": ["upbeat electronic", "energetic dance", "power anthem"]},
    "calm":          {"genre": "Ambient / Lo-fi", "tempo": "slow", "tracks": ["calm ambient", "lo-fi chill", "soft piano"]},
    "dramatic":      {"genre": "Cinematic / Orchestral", "tempo": "medium", "tracks": ["cinematic epic", "dramatic orchestra", "dark thriller"]},
    "funny":         {"genre": "Comedy / Quirky", "tempo": "medium", "tracks": ["fun comedy", "quirky ukulele", "playful background"]},
    "inspirational": {"genre": "Motivational / Pop", "tempo": "medium", "tracks": ["inspirational uplifting", "motivational corporate", "positive pop"]},
    "sad":           {"genre": "Emotional / Classical", "tempo": "slow", "tracks": ["sad piano", "emotional violin", "melancholic ambient"]},
    "happy":         {"genre": "Pop / Upbeat", "tempo": "fast", "tracks": ["happy upbeat", "cheerful pop", "feel good music"]},
    "informative":   {"genre": "Corporate / Neutral", "tempo": "medium", "tracks": ["corporate background", "neutral ambient", "documentary music"]},
    "travel":        {"genre": "World / Adventure", "tempo": "medium", "tracks": ["travel adventure", "world music", "epic journey"]},
    "business":      {"genre": "Corporate / Modern", "tempo": "medium", "tracks": ["corporate professional", "modern business", "success music"]},
    "nature":        {"genre": "Acoustic / Nature", "tempo": "slow", "tracks": ["nature ambient", "acoustic guitar", "forest sounds"]},
    "food":          {"genre": "Jazz / Acoustic", "tempo": "medium", "tracks": ["cooking jazz", "cafe acoustic", "warm background"]},
    "fitness":       {"genre": "Hip-hop / Electronic", "tempo": "fast", "tracks": ["workout hip hop", "gym motivation", "power training"]},
    "tech":          {"genre": "Electronic / Futuristic", "tempo": "medium", "tracks": ["tech electronic", "futuristic ambient", "digital innovation"]},
}

TRANSITION_MOOD_MAP = {
    "energetic":     "cut",
    "calm":          "fade",
    "dramatic":      "dissolve",
    "funny":         "zoom",
    "inspirational": "fade",
    "sad":           "dissolve",
    "happy":         "slide",
    "informative":   "cut",
    "travel":        "dissolve",
    "business":      "fade",
    "nature":        "dissolve",
    "food":          "slide",
    "fitness":       "cut",
    "tech":          "zoom",
}

SFX_MOOD_MAP = {
    "energetic":     "whoosh impact",
    "dramatic":      "dramatic hit",
    "funny":         "comedy boing",
    "inspirational": "soft chime",
    "travel":        "whoosh transition",
    "tech":          "digital beep",
    "fitness":       "impact hit",
    "food":          "sizzle cooking",
}


class FreeScriptAnalyzer:
    def __init__(self):
        self.cache_dir = Path("static/uploads/analysis_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def detect_mood(self, text: str) -> str:
        text_lower = text.lower()
        scores = {}
        for mood, keywords in MOOD_KEYWORDS.items():
            scores[mood] = sum(1 for kw in keywords if kw in text_lower)
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "inspirational"

    def detect_language(self, text: str) -> str:
        try:
            from langdetect import detect
            return detect(text)
        except Exception:
            return "en"

    def extract_broll_keywords(self, sentence: str, mood: str) -> list:
        """Extract meaningful B-roll search keywords from a sentence."""
        import re

        # Remove common stop words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                      "have", "has", "had", "do", "does", "did", "will", "would", "could",
                      "should", "may", "might", "shall", "can", "to", "of", "in", "on",
                      "at", "by", "for", "with", "about", "against", "between", "into",
                      "through", "during", "before", "after", "above", "below", "from",
                      "up", "down", "out", "off", "over", "under", "again", "further",
                      "then", "once", "and", "but", "or", "so", "yet", "both", "either",
                      "neither", "not", "only", "own", "same", "than", "too", "very",
                      "just", "because", "as", "until", "while", "although", "if",
                      "this", "that", "these", "those", "i", "we", "you", "he", "she",
                      "it", "they", "what", "which", "who", "when", "where", "why", "how"}

        # Extract nouns and meaningful words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', sentence.lower())
        keywords = [w for w in words if w not in stop_words]

        # Build compound keywords (pairs)
        result = []
        for i in range(len(keywords) - 1):
            result.append(f"{keywords[i]} {keywords[i+1]}")
        result.extend(keywords[:3])

        # Add mood-based modifier
        mood_modifiers = {
            "travel": ["landscape", "destination", "scenic view"],
            "nature": ["wildlife", "forest", "natural"],
            "tech": ["technology", "digital", "modern"],
            "fitness": ["workout", "gym", "exercise"],
            "food": ["cooking", "restaurant", "delicious"],
            "business": ["office", "professional", "corporate"],
        }
        if mood in mood_modifiers:
            result.extend(mood_modifiers[mood][:1])

        # Clean and deduplicate
        seen = set()
        final = []
        for kw in result[:6]:
            if kw not in seen and len(kw) > 4:
                seen.add(kw)
                final.append(kw)

        return final[:4] if final else [mood, "cinematic", "background"]

    def split_into_scenes(self, script: str, words_per_scene: int = 35) -> list:
        """Split script into scenes based on paragraphs and sentence groups."""
        # First try to split by double newlines (paragraphs)
        paragraphs = [p.strip() for p in script.split('\n\n') if p.strip()]

        if len(paragraphs) < 2:
            # Fall back to sentence splitting
            sentences = re.split(r'(?<=[.!?])\s+', script.strip())
            paragraphs = []
            current = []
            word_count = 0
            for sent in sentences:
                current.append(sent)
                word_count += len(sent.split())
                if word_count >= words_per_scene:
                    paragraphs.append(" ".join(current))
                    current = []
                    word_count = 0
            if current:
                paragraphs.append(" ".join(current))

        return paragraphs

    def estimate_duration(self, text: str, wpm: int = 140) -> float:
        words = len(text.split())
        return round(max(3.0, (words / wpm) * 60), 2)

    def analyze(self, script: str, voice_config: dict = None) -> dict:
        """
        Full free script analysis — no API keys needed!
        Returns structured scene breakdown.
        """
        if not script.strip():
            raise ValueError("Script is empty")

        mood = self.detect_mood(script)
        lang = self.detect_language(script)
        music_info = MUSIC_MOOD_MAP.get(mood, MUSIC_MOOD_MAP["inspirational"])
        transition = TRANSITION_MOOD_MAP.get(mood, "fade")
        sfx = SFX_MOOD_MAP.get(mood)

        # Split into scenes
        raw_scenes = self.split_into_scenes(script)

        scenes = []
        for i, text in enumerate(raw_scenes):
            duration = self.estimate_duration(text)
            broll_keywords = self.extract_broll_keywords(text, mood)

            # Vary transitions a bit
            transitions = [transition, "fade", "dissolve", "cut"]
            scene_transition = transitions[i % len(transitions)]

            scenes.append({
                "id": i + 1,
                "text": text,
                "broll_keywords": broll_keywords,
                "transition": scene_transition,
                "duration": duration,
                "mood": mood,
                "sfx": sfx if i == 0 else None,  # SFX on first scene
                "music_mood": mood
            })

        total_duration = sum(s["duration"] for s in scenes)

        return {
            "title": self._generate_title(script),
            "mood": mood,
            "language": lang,
            "overall_theme": f"A {mood} video with {len(scenes)} scenes",
            "duration_estimate": int(total_duration),
            "scenes": scenes,
            "music": {
                "genre": music_info["genre"],
                "mood": mood,
                "tempo": music_info["tempo"],
                "suggested_tracks": music_info["tracks"]
            },
            "voiceover": {
                "tone": "natural",
                "pace": "normal",
                "emotion": mood
            },
            "captions_style": {
                "position": "bottom",
                "highlight_color": "#FFFF00",
                "font_size": "medium"
            }
        }

    def _generate_title(self, script: str) -> str:
        """Generate a simple title from the first line of the script."""
        first_line = script.strip().split('\n')[0][:60]
        words = first_line.split()[:6]
        return " ".join(words).rstrip(".,!?:;") if words else "My Video"
