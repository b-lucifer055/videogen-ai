"""
Script Analyzer - Uses AI to break down the script into scenes,
detect mood, extract keywords for B-roll, suggest music & SFX.
"""

import json
import os
import re
from openai import OpenAI


class ScriptAnalyzer:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def analyze(self, script: str, voice_style: str = "neutral") -> dict:
        """
        Full script analysis returning structured JSON:
        {
          "title": str,
          "mood": str,
          "overall_theme": str,
          "duration_estimate": int,  # seconds
          "scenes": [
            {
              "id": int,
              "text": str,
              "broll_keywords": [str],
              "transition": str,
              "duration": float,
              "mood": str,
              "sfx": str | None,
              "music_mood": str
            }
          ],
          "music": {
            "genre": str,
            "mood": str,
            "tempo": str,
            "suggested_tracks": [str]
          },
          "voiceover": {
            "tone": str,
            "pace": str,
            "emotion": str
          }
        }
        """
        prompt = f"""You are a professional video editor and script analyzer.
Analyze the following script and break it into scenes for a video production pipeline.

Script:
\"\"\"
{script}
\"\"\"

Voice style preference: {voice_style}

Return a comprehensive JSON object with this EXACT structure (no markdown, pure JSON):
{{
  "title": "video title",
  "mood": "overall mood (e.g., energetic, calm, dramatic, funny, inspirational)",
  "overall_theme": "brief theme description",
  "duration_estimate": <estimated total seconds>,
  "scenes": [
    {{
      "id": 1,
      "text": "exact script text for this scene",
      "broll_keywords": ["keyword1", "keyword2", "keyword3"],
      "transition": "fade | dissolve | wipe | zoom | slide | cut | none",
      "duration": <seconds as float>,
      "mood": "scene mood",
      "sfx": "sound effect description or null",
      "music_mood": "upbeat | calm | tense | dramatic | happy | sad | neutral"
    }}
  ],
  "music": {{
    "genre": "genre name",
    "mood": "mood",
    "tempo": "slow | medium | fast",
    "suggested_tracks": ["track keyword 1", "track keyword 2", "track keyword 3"]
  }},
  "voiceover": {{
    "tone": "professional | casual | dramatic | friendly | authoritative",
    "pace": "slow | normal | fast",
    "emotion": "emotion description"
  }},
  "captions_style": {{
    "position": "bottom | top | center",
    "highlight_color": "#hex_color",
    "font_size": "small | medium | large"
  }}
}}

Rules:
- Split script into logical scenes (1-3 sentences per scene usually)
- Each scene should be 3-8 seconds
- B-roll keywords must be specific and searchable (e.g., "busy city street night", not just "city")
- Transitions should match the mood and flow
- SFX should be descriptive (e.g., "whoosh transition", "keyboard typing", "crowd cheering") or null
- Duration should match realistic speaking pace (~130-150 words per minute)
"""

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        raw = response.choices[0].message.content
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ValueError("Could not parse AI response as JSON")

        return data

    def get_broll_queries(self, scene: dict) -> list:
        """Extract B-roll search queries from scene analysis."""
        keywords = scene.get("broll_keywords", [])
        return keywords[:3]  # Top 3 queries per scene

    def estimate_word_count(self, text: str) -> int:
        return len(text.split())

    def estimate_duration(self, text: str, wpm: int = 140) -> float:
        words = self.estimate_word_count(text)
        return round((words / wpm) * 60, 2)
