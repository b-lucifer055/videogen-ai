"""
Video Composer - The core engine that assembles all assets into
the final video using MoviePy. Supports multiple output formats.
"""

import os
import json
import time
import tempfile
import subprocess
from pathlib import Path
import numpy as np


# ── Video Size Presets ───────────────────────────────────────────────────────
VIDEO_SIZES = {
    "landscape_1080p": {"width": 1920, "height": 1080, "label": "Landscape 1080p (YouTube)"},
    "landscape_720p":  {"width": 1280, "height": 720,  "label": "Landscape 720p"},
    "portrait_1080":   {"width": 1080, "height": 1920, "label": "Portrait 9:16 (Reels/TikTok)"},
    "portrait_720":    {"width": 720,  "height": 1280, "label": "Portrait 9:16 720p"},
    "square_1080":     {"width": 1080, "height": 1080, "label": "Square 1:1 (Instagram Post)"},
    "square_720":      {"width": 720,  "height": 720,  "label": "Square 720p"},
    "widescreen_4k":   {"width": 3840, "height": 2160, "label": "4K Widescreen"},
    "twitter":         {"width": 1280, "height": 720,  "label": "Twitter/X Video"},
}

TRANSITION_TYPES = {
    "fade": "fade",
    "dissolve": "crossfadeout",
    "cut": "none",
    "wipe": "wipeleft",
    "zoom": "zoompan",
    "slide": "slideleft",
    "none": "none"
}


class VideoComposer:
    def __init__(self):
        self.output_dir = Path("static/outputs")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = Path("static/uploads/temp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_video_size(self, size_preset: str) -> tuple:
        """Get (width, height) for a given preset."""
        size = VIDEO_SIZES.get(size_preset, VIDEO_SIZES["landscape_1080p"])
        return size["width"], size["height"]

    def check_ffmpeg(self) -> bool:
        """Check if ffmpeg is installed."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def create_solid_color_clip(self, color: tuple, width: int, height: int,
                                 duration: float, output_path: str) -> str:
        """Create a solid color video clip using ffmpeg."""
        r, g, b = color
        color_hex = f"#{r:02x}{g:02x}{b:02x}"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={color_hex}:size={width}x{height}:rate=30:duration={duration}",
            "-c:v", "libx264",
            "-t", str(duration),
            output_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        return output_path

    def create_text_overlay_clip(self, text: str, width: int, height: int,
                                  duration: float, output_path: str,
                                  font_size: int = 48, color: str = "white") -> str:
        """Create a text overlay clip using ffmpeg drawtext filter."""
        # Escape special characters for ffmpeg
        safe_text = text.replace("'", "\\'").replace(":", "\\:")
        filter_str = (
            f"color=black:size={width}x{height}:rate=30,"
            f"drawtext=text='{safe_text}':fontcolor={color}:fontsize={font_size}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0,{duration})'"
        )
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", filter_str,
            "-t", str(duration),
            "-c:v", "libx264",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        return output_path

    def prepare_video_clip(self, video_path: str, width: int, height: int,
                            duration: float, output_path: str) -> str | None:
        """
        Prepare a video clip: resize, crop, trim to duration.
        Uses ffmpeg for reliability.
        """
        if not video_path or not Path(video_path).exists():
            return None

        # Scale and crop to fill target dimensions (smart crop to center)
        vf_filter = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",   # Loop if clip is shorter than duration
            "-i", video_path,
            "-t", str(duration),
            "-vf", vf_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-an",                   # Remove audio from B-roll
            "-r", "30",
            output_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0 and Path(output_path).exists():
                return output_path
            print(f"[Composer] ffmpeg clip error: {result.stderr.decode()[:200]}")
        except Exception as e:
            print(f"[Composer] Clip preparation error: {e}")

        return None

    def add_fade_transition(self, clip_path: str, duration: float,
                             fade_in: bool = True, fade_out: bool = True,
                             fade_duration: float = 0.5) -> str:
        """Add fade in/out to a clip."""
        filters = []
        if fade_in:
            filters.append(f"fade=t=in:st=0:d={fade_duration}")
        if fade_out:
            filters.append(f"fade=t=out:st={duration - fade_duration}:d={fade_duration}")

        if not filters:
            return clip_path

        output_path = clip_path.replace(".mp4", "_faded.mp4")
        vf = ",".join(filters)
        cmd = [
            "ffmpeg", "-y", "-i", clip_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        if result.returncode == 0:
            return output_path
        return clip_path

    def add_captions_to_video(self, video_path: str, srt_path: str,
                               output_path: str, style: dict) -> str:
        """Burn captions into video using ffmpeg subtitles filter."""
        position = style.get("position", "bottom")
        font_size = {"small": 24, "medium": 32, "large": 44}.get(
            style.get("font_size", "medium"), 32
        )
        color = style.get("highlight_color", "#FFFFFF").lstrip("#")

        # Margin based on position
        margin_v = {"bottom": 80, "top": 80, "center": 0}.get(position, 80)

        subtitle_filter = (
            f"subtitles={srt_path}:force_style="
            f"'FontSize={font_size},PrimaryColour=&H00{color[::-1]},"  
            f"Outline=2,OutlineColour=&H00000000,MarginV={margin_v}'"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", subtitle_filter,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "copy",
            output_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode == 0 and Path(output_path).exists():
                return output_path
            print(f"[Captions] Error: {result.stderr.decode()[:300]}")
        except Exception as e:
            print(f"[Captions] Exception: {e}")

        return video_path  # Return original if captions fail

    def concat_clips(self, clip_paths: list, output_path: str) -> str | None:
        """Concatenate multiple video clips using ffmpeg concat."""
        if not clip_paths:
            return None

        # Write concat list file
        concat_file = str(self.temp_dir / "concat_list.txt")
        with open(concat_file, "w") as f:
            for path in clip_paths:
                if path and Path(path).exists():
                    f.write(f"file '{os.path.abspath(path)}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            output_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode == 0 and Path(output_path).exists():
                return output_path
            print(f"[Concat] Error: {result.stderr.decode()[:300]}")
        except Exception as e:
            print(f"[Concat] Exception: {e}")

        return None

    def mix_audio(self, video_path: str, voiceover_path: str,
                  music_path: str | None, output_path: str,
                  music_volume: float = 0.15, voice_volume: float = 1.0) -> str:
        """
        Mix voiceover + background music into the video.
        """
        inputs = ["-i", video_path, "-i", voiceover_path]
        filter_parts = [f"[1:a]volume={voice_volume}[voice]"]
        audio_mix = "[voice]"

        if music_path and Path(music_path).exists():
            inputs += ["-i", music_path]
            filter_parts.append(
                f"[2:a]volume={music_volume},aloop=loop=-1:size=2e+09[music]"
            )
            filter_parts.append(
                f"[voice][music]amix=inputs=2:duration=first:dropout_transition=3[aout]"
            )
            audio_mix = "[aout]"
        else:
            filter_parts.append(f"[voice]aresample=44100[aout]")
            audio_mix = "[aout]"

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
        ] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", audio_mix,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode == 0 and Path(output_path).exists():
                return output_path
            print(f"[Audio Mix] Error: {result.stderr.decode()[:300]}")
        except Exception as e:
            print(f"[Audio Mix] Exception: {e}")

        return video_path

    def create_fallback_clip(self, scene: dict, width: int, height: int,
                              duration: float, output_path: str) -> str:
        """
        Create a beautiful gradient/animated fallback clip when no B-roll is available.
        """
        mood = scene.get("mood", "neutral")
        text = scene.get("broll_keywords", [""])[0] if scene.get("broll_keywords") else ""

        # Mood-based color palettes
        MOOD_COLORS = {
            "energetic": ("FF6B35", "F7931E"),
            "calm": ("667eea", "764ba2"),
            "dramatic": ("1a1a2e", "16213e"),
            "funny": ("f9ca24", "f0932b"),
            "inspirational": ("6c63ff", "3f3d56"),
            "sad": ("2c3e50", "3498db"),
            "happy": ("fc5c7d", "6a3093"),
            "tense": ("0f0c29", "302b63"),
            "neutral": ("373B44", "4286f4"),
        }

        colors = MOOD_COLORS.get(mood, MOOD_COLORS["neutral"])
        c1, c2 = colors

        # Use lavfi gradient effect
        filter_str = (
            f"gradients=size={width}x{height}:speed=0.3:c0=0x{c1}:c1=0x{c2}:x0=0:y0=0:x1={width}:y1={height}"
        )

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", filter_str,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-r", "30",
            output_path
        ]

        # Try gradients first, fallback to simple color
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            # Simple color fallback
            self.create_solid_color_clip((30, 30, 60), width, height, duration, output_path)

        # Add text overlay if we have keywords
        if text:
            overlay_path = output_path.replace(".mp4", "_text.mp4")
            safe_text = text[:40].replace("'", "").replace(":", "")
            text_cmd = [
                "ffmpeg", "-y",
                "-i", output_path,
                "-vf", (
                    f"drawtext=text='{safe_text}':fontcolor=white:fontsize={max(24, width//30)}:"
                    f"x=(w-text_w)/2:y=(h-text_h)/2:alpha=0.7:"
                    f"box=1:boxcolor=black@0.3:boxborderw=10"
                ),
                "-c:v", "libx264",
                "-preset", "fast",
                overlay_path
            ]
            result2 = subprocess.run(text_cmd, capture_output=True, timeout=30)
            if result2.returncode == 0:
                return overlay_path

        return output_path

    def compose(self, job_id: str, analysis: dict, broll_clips: dict,
                voiceover_path: str | None, music_path: str | None,
                sfx_clips: dict, captions: list, config: dict,
                progress_callback=None) -> str | None:
        """
        Main composition method. Assembles everything into the final video.

        config: {
          size: str,           # video size preset
          music_volume: float, # 0.0 - 1.0
          voice_volume: float, # 0.0 - 1.0
          add_captions: bool,
          captions_style: dict,
          quality: str,        # "draft" | "standard" | "high"
        }
        """
        scenes = analysis.get("scenes", [])
        if not scenes:
            return None

        size_preset = config.get("size", "landscape_1080p")
        width, height = self.get_video_size(size_preset)
        add_captions = config.get("add_captions", True)
        music_volume = config.get("music_volume", 0.15)
        voice_volume = config.get("voice_volume", 1.0)
        captions_style = config.get("captions_style", analysis.get("captions_style", {}))

        job_dir = self.temp_dir / job_id
        job_dir.mkdir(exist_ok=True)

        def _progress(step, current, total, message):
            if progress_callback:
                progress_callback(step=step, current=current, total=total, message=message)

        # ── Step 1: Prepare individual scene clips ────────────────────────
        _progress("compose", 0, 10, "Preparing scene clips...")
        prepared_clips = []
        total_scenes = len(scenes)

        for i, scene in enumerate(scenes):
            scene_id = scene["id"]
            duration = scene.get("duration", 5.0)
            broll_path = broll_clips.get(scene_id)

            scene_output = str(job_dir / f"scene_{scene_id:03d}.mp4")
            transition = scene.get("transition", "fade")

            _progress("compose", i, total_scenes,
                      f"Processing scene {i+1}/{total_scenes}...")

            # Try to prepare the B-roll clip
            prepared = None
            if broll_path and Path(broll_path).exists():
                prepared = self.prepare_video_clip(
                    broll_path, width, height, duration, scene_output
                )

            # Fallback to generated clip
            if not prepared:
                prepared = self.create_fallback_clip(
                    scene, width, height, duration, scene_output
                )

            # Apply transition
            if transition in ("fade", "dissolve") and prepared:
                prepared = self.add_fade_transition(
                    prepared, duration,
                    fade_in=(i > 0),
                    fade_out=(i < total_scenes - 1),
                    fade_duration=0.4
                )

            if prepared:
                prepared_clips.append(prepared)

        if not prepared_clips:
            return None

        # ── Step 2: Concatenate all clips ─────────────────────────────────
        _progress("compose", 7, 10, "Concatenating clips...")
        raw_video = str(job_dir / "raw_video.mp4")
        concatenated = self.concat_clips(prepared_clips, raw_video)

        if not concatenated:
            return None

        # ── Step 3: Mix audio ─────────────────────────────────────────────
        _progress("compose", 8, 10, "Mixing audio...")
        mixed_video = str(job_dir / "mixed_video.mp4")

        if voiceover_path and Path(voiceover_path).exists():
            final_with_audio = self.mix_audio(
                concatenated, voiceover_path,
                music_path, mixed_video,
                music_volume=music_volume,
                voice_volume=voice_volume
            )
        else:
            final_with_audio = concatenated

        # ── Step 4: Add captions ──────────────────────────────────────────
        final_video = final_with_audio

        if add_captions and captions:
            _progress("compose", 9, 10, "Burning in captions...")
            srt_path = str(job_dir / "captions.srt")
            from utils.caption_generator import CaptionGenerator
            cap_gen = CaptionGenerator()
            cap_gen.save_srt(captions, srt_path)

            captioned_path = str(job_dir / "captioned_video.mp4")
            final_video = self.add_captions_to_video(
                final_with_audio, srt_path, captioned_path, captions_style
            )

        # ── Step 5: Move to outputs ───────────────────────────────────────
        _progress("compose", 10, 10, "Finalizing video...")
        output_filename = f"{job_id}_{size_preset}.mp4"
        output_path = str(self.output_dir / output_filename)

        import shutil
        shutil.copy2(final_video, output_path)

        return output_path
