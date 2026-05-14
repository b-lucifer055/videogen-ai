"""
Caption Generator - Creates SRT/ASS subtitles from audio using
OpenAI Whisper, then formats them for different video styles.
"""

import os
import json
import re
from pathlib import Path
from openai import OpenAI


class CaptionGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.cache_dir = Path("static/uploads/caption_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def transcribe_audio(self, audio_path: str) -> dict:
        """
        Use OpenAI Whisper to transcribe audio with word-level timestamps.
        Returns Whisper verbose_json response.
        """
        try:
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["word", "segment"]
                )
            return response.model_dump()
        except Exception as e:
            print(f"[Captions] Whisper error: {e}")
            return {}

    def generate_from_script(self, script_text: str, scenes: list) -> list:
        """
        Generate captions directly from script and scene timings
        (used when Whisper isn't available or for preview).
        Returns list of caption segments.
        """
        captions = []
        current_time = 0.0

        for scene in scenes:
            text = scene.get("text", "")
            duration = scene.get("duration", 5.0)
            words = text.split()
            if not words:
                current_time += duration
                continue

            words_per_caption = 5  # ~5 words per caption line for reels
            word_duration = duration / max(len(words), 1)

            for i in range(0, len(words), words_per_caption):
                chunk = words[i:i + words_per_caption]
                chunk_text = " ".join(chunk)
                chunk_duration = len(chunk) * word_duration

                captions.append({
                    "start": round(current_time, 3),
                    "end": round(current_time + chunk_duration, 3),
                    "text": chunk_text,
                    "words": chunk
                })
                current_time += chunk_duration

        return captions

    def generate_from_whisper(self, audio_path: str) -> list:
        """Generate captions using Whisper with accurate timestamps."""
        transcript = self.transcribe_audio(audio_path)
        if not transcript:
            return []

        segments = transcript.get("segments", [])
        captions = []

        for seg in segments:
            words = seg.get("words", [])
            if not words:
                captions.append({
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 0),
                    "text": seg.get("text", "").strip(),
                    "words": [seg.get("text", "").strip()]
                })
                continue

            # Group into ~5-word chunks for reels-style captions
            chunk_size = 5
            for i in range(0, len(words), chunk_size):
                chunk = words[i:i + chunk_size]
                if chunk:
                    captions.append({
                        "start": chunk[0].get("start", 0),
                        "end": chunk[-1].get("end", 0),
                        "text": " ".join(w.get("word", "").strip() for w in chunk),
                        "words": [w.get("word", "").strip() for w in chunk]
                    })

        return captions

    def to_srt(self, captions: list) -> str:
        """Convert captions to SRT format."""
        srt_lines = []
        for i, cap in enumerate(captions, 1):
            start = self._seconds_to_srt_time(cap["start"])
            end = self._seconds_to_srt_time(cap["end"])
            srt_lines.append(f"{i}\n{start} --> {end}\n{cap['text']}\n")
        return "\n".join(srt_lines)

    def to_ass(self, captions: list, style: dict) -> str:
        """Convert captions to ASS format with custom styling."""
        position = style.get("position", "bottom")
        font_size = {"small": 28, "medium": 36, "large": 48}.get(
            style.get("font_size", "medium"), 36
        )
        highlight_color = style.get("highlight_color", "#FFFF00")
        color_bgr = self._hex_to_ass_color(highlight_color)

        # Position: bottom=2, top=8, center=5 (ASS alignment)
        alignment = {"bottom": 2, "top": 8, "center": 5}.get(position, 2)

        ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,{alignment},20,20,50,1
Style: Highlight,Arial,{font_size},{color_bgr},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,{alignment},20,20,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        events = []
        for cap in captions:
            start = self._seconds_to_ass_time(cap["start"])
            end = self._seconds_to_ass_time(cap["end"])
            text = cap["text"].replace("\n", "\\N")
            events.append(
                f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}"
            )

        return ass_header + "\n".join(events)

    def _seconds_to_srt_time(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _seconds_to_ass_time(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    def _hex_to_ass_color(self, hex_color: str) -> str:
        """Convert #RRGGBB to ASS &H00BBGGRR format."""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r, g, b = hex_color[:2], hex_color[2:4], hex_color[4:6]
            return f"&H00{b}{g}{r}"
        return "&H0000FFFF"

    def save_srt(self, captions: list, output_path: str) -> str:
        """Save captions as SRT file."""
        srt_content = self.to_srt(captions)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        return output_path

    def save_ass(self, captions: list, style: dict, output_path: str) -> str:
        """Save captions as ASS file."""
        ass_content = self.to_ass(captions, style)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)
        return output_path
