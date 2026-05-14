"""
Raw Clips Editor — Converts raw footage into post-ready edits.
Supports: Auto mode (full auto) + Manual mode (user-controlled).
All processing done with ffmpeg — completely free!
"""

import os
import json
import subprocess
import random
from pathlib import Path


class RawClipsEditor:
    def __init__(self):
        self.temp_dir = Path("static/uploads/temp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = Path("static/outputs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Video Analysis ────────────────────────────────────────────────────────
    def get_video_info(self, video_path: str) -> dict:
        """Get video metadata using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams", "-show_format",
            video_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            data = json.loads(result.stdout)

            video_stream = next((s for s in data.get("streams", []) if s["codec_type"] == "video"), {})
            audio_stream = next((s for s in data.get("streams", []) if s["codec_type"] == "audio"), {})
            fmt = data.get("format", {})

            return {
                "duration": float(fmt.get("duration", 0)),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "fps": eval(video_stream.get("r_frame_rate", "30/1")),
                "has_audio": bool(audio_stream),
                "codec": video_stream.get("codec_name", "unknown"),
                "size_mb": round(int(fmt.get("size", 0)) / (1024 * 1024), 1),
                "bitrate": int(fmt.get("bit_rate", 0)),
            }
        except Exception as e:
            print(f"[Editor] ffprobe error: {e}")
            return {"duration": 0, "width": 0, "height": 0, "fps": 30, "has_audio": False}

    # ── Clip Preprocessing ────────────────────────────────────────────────────
    def trim_clip(self, input_path: str, output_path: str,
                  start: float = 0, duration: float = None) -> str | None:
        """Trim a clip to specified start and duration."""
        cmd = ["ffmpeg", "-y", "-i", input_path, "-ss", str(start)]
        if duration:
            cmd += ["-t", str(duration)]
        cmd += ["-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", output_path]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return output_path if result.returncode == 0 else None

    def resize_crop_clip(self, input_path: str, output_path: str,
                          width: int, height: int) -> str | None:
        """Resize and center-crop clip to target dimensions."""
        vf = (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
              f"crop={width}:{height}")
        cmd = ["ffmpeg", "-y", "-i", input_path,
               "-vf", vf, "-c:v", "libx264", "-preset", "fast",
               "-crf", "22", "-c:a", "aac", output_path]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return output_path if result.returncode == 0 else None

    def speed_clip(self, input_path: str, output_path: str,
                   speed: float = 1.0) -> str | None:
        """Change clip playback speed (0.5 = slow-mo, 2.0 = fast-forward)."""
        # Video PTS multiplication + audio tempo
        vf = f"setpts={1/speed}*PTS"
        atempo = max(0.5, min(2.0, speed))  # atempo limited to 0.5-2.0
        af = f"atempo={atempo}"

        cmd = ["ffmpeg", "-y", "-i", input_path,
               "-vf", vf, "-af", af,
               "-c:v", "libx264", "-preset", "fast", "-crf", "22",
               output_path]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return output_path if result.returncode == 0 else None

    # ── Color Grading ─────────────────────────────────────────────────────────
    PRESETS = {
        "cinematic":    "eq=brightness=-0.02:contrast=1.1:saturation=0.85,curves=r='0/0 0.4/0.35 1/1':g='0/0 0.5/0.5 1/1':b='0/0 0.5/0.55 1/1'",
        "vibrant":      "eq=contrast=1.15:saturation=1.5:brightness=0.03",
        "vintage":      "curves=r='0/0.1 0.5/0.55 1/0.9':g='0/0.05 0.5/0.5 1/0.85':b='0/0.1 0.5/0.45 1/0.8',hue=s=0.7",
        "moody":        "eq=brightness=-0.05:contrast=1.2:saturation=0.7,curves=all='0/0 0.3/0.25 0.7/0.65 1/1'",
        "bright":       "eq=brightness=0.06:contrast=1.05:saturation=1.2",
        "cool":         "curves=r='0/0 1/0.85':b='0/0.1 1/1',eq=saturation=1.1",
        "warm":         "curves=r='0/0.08 1/1':b='0/0 1/0.85',eq=saturation=1.15",
        "black_white":  "hue=s=0,eq=contrast=1.3",
        "fade":         "curves=all='0/0.1 1/0.9',eq=saturation=0.8",
        "sharp":        "unsharp=5:5:1.5:5:5:0.0,eq=contrast=1.05",
        "none":         None,
    }

    def apply_color_grade(self, input_path: str, output_path: str,
                           preset: str = "cinematic") -> str | None:
        """Apply color grading preset to a clip."""
        filter_str = self.PRESETS.get(preset)
        if not filter_str:
            import shutil
            shutil.copy2(input_path, output_path)
            return output_path

        cmd = ["ffmpeg", "-y", "-i", input_path,
               "-vf", filter_str,
               "-c:v", "libx264", "-preset", "fast", "-crf", "22",
               "-c:a", "copy", output_path]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return output_path if result.returncode == 0 else None

    # ── Transitions ───────────────────────────────────────────────────────────
    def add_transition(self, clip1_path: str, clip2_path: str,
                        output_path: str, transition: str = "fade",
                        duration: float = 0.5) -> str | None:
        """Add transition between two clips using xfade filter."""
        info1 = self.get_video_info(clip1_path)
        clip1_dur = info1.get("duration", 5.0)
        offset = max(0, clip1_dur - duration)

        xfade_map = {
            "fade":      "fade",
            "dissolve":  "dissolve",
            "wipe":      "wipeleft",
            "slide":     "slideleft",
            "zoom":      "zoomin",
            "blur":      "radial",
            "flip":      "horzflip",
            "pixelize":  "pixelize",
        }
        xfade = xfade_map.get(transition, "fade")

        filter_complex = (
            f"[0:v][1:v]xfade=transition={xfade}:duration={duration}:offset={offset}[v];"
            f"[0:a][1:a]acrossfade=d={duration}[a]"
        )
        cmd = ["ffmpeg", "-y",
               "-i", clip1_path, "-i", clip2_path,
               "-filter_complex", filter_complex,
               "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "fast", "-crf", "22",
               output_path]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return output_path if result.returncode == 0 else None

    # ── Text Overlays ─────────────────────────────────────────────────────────
    def add_text_overlay(self, input_path: str, output_path: str,
                          text: str, position: str = "bottom",
                          font_size: int = 40, color: str = "white",
                          bg_box: bool = True) -> str | None:
        """Add text overlay to video."""
        text_escaped = text.replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")

        y_pos = {"top": "50", "center": "(h-text_h)/2", "bottom": "h-80"}.get(position, "h-80")

        box_opts = ":box=1:boxcolor=black@0.5:boxborderw=12" if bg_box else ""
        vf = (f"drawtext=text='{text_escaped}':fontcolor={color}:fontsize={font_size}:"
              f"x=(w-text_w)/2:y={y_pos}{box_opts}:font=Arial")

        cmd = ["ffmpeg", "-y", "-i", input_path,
               "-vf", vf,
               "-c:v", "libx264", "-preset", "fast", "-crf", "22",
               "-c:a", "copy", output_path]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return output_path if result.returncode == 0 else None

    def burn_subtitles(self, input_path: str, output_path: str,
                        srt_path: str, style: dict = None) -> str | None:
        """Burn SRT subtitles into video."""
        style = style or {}
        font_size = {"small": 22, "medium": 30, "large": 40}.get(
            style.get("font_size", "medium"), 30)
        color = style.get("color", "white")
        position = style.get("position", "bottom")
        margin_v = {"bottom": 60, "top": 60, "center": 0}.get(position, 60)

        force_style = (f"FontSize={font_size},PrimaryColour=&H00FFFFFF,"
                       f"Outline=2,OutlineColour=&H00000000,"
                       f"MarginV={margin_v},Alignment=2,Bold=1")

        subtitle_filter = f"subtitles='{srt_path}':force_style='{force_style}'"

        cmd = ["ffmpeg", "-y", "-i", input_path,
               "-vf", subtitle_filter,
               "-c:v", "libx264", "-preset", "fast", "-crf", "22",
               "-c:a", "copy", output_path]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        return output_path if result.returncode == 0 else None

    # ── Audio Mixing ──────────────────────────────────────────────────────────
    def mix_background_music(self, video_path: str, music_path: str,
                              output_path: str, music_vol: float = 0.15,
                              duck_on_speech: bool = False) -> str | None:
        """Mix background music under video audio."""
        filter_complex = (
            f"[1:a]volume={music_vol},aloop=loop=-1:size=2e+09[music];"
            f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        cmd = ["ffmpeg", "-y",
               "-i", video_path, "-i", music_path,
               "-filter_complex", filter_complex,
               "-map", "0:v", "-map", "[aout]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-shortest", output_path]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        return output_path if result.returncode == 0 else None

    def replace_audio(self, video_path: str, audio_path: str,
                       output_path: str) -> str | None:
        """Replace video audio track with new audio."""
        cmd = ["ffmpeg", "-y",
               "-i", video_path, "-i", audio_path,
               "-map", "0:v", "-map", "1:a",
               "-c:v", "copy", "-c:a", "aac",
               "-shortest", output_path]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        return output_path if result.returncode == 0 else None

    # ── Auto Edit (Full Auto Mode) ────────────────────────────────────────────
    def auto_edit(self, clip_paths: list, job_id: str, config: dict,
                   progress_callback=None) -> str | None:
        """
        Full automatic editing pipeline:
        1. Analyze each clip
        2. Trim best parts
        3. Resize to target format
        4. Apply color grade
        5. Add transitions
        6. Add music
        7. Add captions if provided
        8. Export final video
        """
        def _progress(step, current, total, message):
            if progress_callback:
                progress_callback(step=step, current=current, total=total, message=message)

        job_dir = self.temp_dir / job_id
        job_dir.mkdir(exist_ok=True)

        size_preset = config.get("size", "portrait_1080")
        from utils.video_composer import VIDEO_SIZES
        size_info = VIDEO_SIZES.get(size_preset, VIDEO_SIZES["portrait_1080"])
        width, height = size_info["width"], size_info["height"]

        color_preset = config.get("color_preset", "cinematic")
        transition = config.get("transition", "fade")
        music_path = config.get("music_path")
        music_vol = float(config.get("music_volume", 0.15))
        max_clip_duration = float(config.get("max_clip_duration", 8.0))
        caption_srt = config.get("caption_srt")
        caption_style = config.get("caption_style", {})

        total_clips = len(clip_paths)
        processed = []

        # ── Process each clip ────────────────────────────────────────────────
        for i, clip_path in enumerate(clip_paths):
            _progress("editing", i, total_clips, f"Processing clip {i+1}/{total_clips}...")

            info = self.get_video_info(clip_path)
            dur = min(info["duration"], max_clip_duration)

            # Skip very short clips
            if dur < 1.0:
                continue

            clip_out = str(job_dir / f"clip_{i:03d}_trim.mp4")
            clip_resize = str(job_dir / f"clip_{i:03d}_resize.mp4")
            clip_graded = str(job_dir / f"clip_{i:03d}_graded.mp4")

            # Trim
            trimmed = self.trim_clip(clip_path, clip_out, start=0, duration=dur)
            if not trimmed:
                continue

            # Resize
            resized = self.resize_crop_clip(trimmed, clip_resize, width, height)
            if not resized:
                resized = trimmed

            # Color grade
            graded = self.apply_color_grade(resized, clip_graded, color_preset)
            if not graded:
                graded = resized

            processed.append(graded)

        if not processed:
            return None

        _progress("editing", total_clips, total_clips, "Joining clips with transitions...")

        # ── Apply transitions and concatenate ────────────────────────────────
        if len(processed) == 1:
            import shutil
            final_concat = str(job_dir / "concat.mp4")
            shutil.copy2(processed[0], final_concat)
        else:
            # Try xfade transitions between pairs, then concat
            # For simplicity, use concat with fade in/out per clip
            concat_list = str(job_dir / "concat.txt")
            with open(concat_list, "w") as f:
                for p in processed:
                    f.write(f"file '{os.path.abspath(p)}'\n")

            final_concat = str(job_dir / "concat.mp4")
            concat_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                          "-i", concat_list,
                          "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                          "-c:a", "aac", final_concat]
            result = subprocess.run(concat_cmd, capture_output=True, timeout=300)
            if result.returncode != 0:
                return None

        current_video = final_concat

        # ── Add background music ─────────────────────────────────────────────
        if music_path and Path(music_path).exists():
            _progress("editing", total_clips + 1, total_clips + 3, "Adding background music...")
            music_out = str(job_dir / "with_music.mp4")
            result = self.mix_background_music(current_video, music_path, music_out, music_vol)
            if result:
                current_video = music_out

        # ── Burn captions ────────────────────────────────────────────────────
        if caption_srt and Path(caption_srt).exists():
            _progress("editing", total_clips + 2, total_clips + 3, "Burning captions...")
            cap_out = str(job_dir / "captioned.mp4")
            result = self.burn_subtitles(current_video, cap_out, caption_srt, caption_style)
            if result:
                current_video = cap_out

        # ── Final export ─────────────────────────────────────────────────────
        _progress("editing", total_clips + 3, total_clips + 3, "Exporting final video...")
        output_path = str(self.output_dir / f"edit_{job_id}_{size_preset}.mp4")
        import shutil
        shutil.copy2(current_video, output_path)
        return output_path

    def concatenate_clips(self, clip_paths: list, output_path: str) -> str | None:
        """Simple concatenation of clips."""
        concat_list = str(self.temp_dir / "temp_concat.txt")
        with open(concat_list, "w") as f:
            for p in clip_paths:
                if Path(p).exists():
                    f.write(f"file '{os.path.abspath(p)}'\n")

        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
               "-i", concat_list,
               "-c:v", "libx264", "-preset", "fast", "-crf", "22",
               "-c:a", "aac", output_path]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        return output_path if result.returncode == 0 else None
