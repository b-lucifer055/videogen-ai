"""
Audio → Full Video Pipeline
Upload audio → Whisper transcribes it (Hindi/Nepali/English) →
Fetches B-roll matching content → Adds captions → Full video
"""

import os
import threading
from pathlib import Path

from utils.multilingual_transcriber import MultilingualTranscriber
from utils.free_script_analyzer import FreeScriptAnalyzer
from utils.free_broll import FreeBRollFetcher, FreeMusicFetcher
from utils.raw_clips_editor import RawClipsEditor
from utils.video_composer import VideoComposer
from utils.job_manager import JobManager


class AudioToVideoPipeline:
    def __init__(self, job_manager: JobManager, socketio=None):
        self.job_manager = job_manager
        self.socketio = socketio

    def emit(self, job_id, step, current, total, message):
        self.job_manager.update_progress(job_id, step, current, total, message)
        if self.socketio:
            job = self.job_manager.get_job(job_id)
            self.socketio.emit("progress", {
                "job_id": job_id, "step": step, "current": current,
                "total": total, "message": message,
                "progress": job["progress"] if job else 0
            })

    def run_in_background(self, job_id: str, audio_path: str, config: dict):
        thread = threading.Thread(
            target=self._safe_run, args=(job_id, audio_path, config), daemon=True
        )
        thread.start()

    def _safe_run(self, job_id, audio_path, config):
        try:
            self._execute(job_id, audio_path, config)
        except Exception as e:
            import traceback
            self.job_manager.fail_job(job_id, str(e))
            print(f"[AudioPipeline] ERROR: {traceback.format_exc()}")
            if self.socketio:
                self.socketio.emit("job_failed", {"job_id": job_id, "error": str(e)})

    def _execute(self, job_id, audio_path, config):
        def p(step, cur, tot, msg):
            self.emit(job_id, step, cur, tot, msg)

        sizes = config.get("sizes", ["portrait_1080"])
        lang = config.get("language")       # None = auto-detect
        add_captions = config.get("add_captions", True)
        translate_captions = config.get("translate", False)
        music_volume = config.get("music_volume", 0.15)
        caption_style_pref = config.get("caption_style", "reels")
        add_bgm = config.get("add_bgm", True)

        # 1 ── Language Detection ─────────────────────────────────────────────
        p("detecting", 0, 1, "🔍 Detecting language from audio...")
        transcriber = MultilingualTranscriber()

        if not lang:
            lang_info = transcriber.detect_language(audio_path)
            lang = lang_info.get("language", "en")
            lang_name = lang_info.get("name", "English")
            lang_flag = lang_info.get("flag", "🌐")
            confidence = lang_info.get("confidence", 0)
            p("detecting", 1, 1,
              f"✅ Detected: {lang_flag} {lang_name} ({round(confidence*100)}% confidence)")
        else:
            from utils.multilingual_transcriber import SUPPORTED_LANGUAGES
            lang_info = SUPPORTED_LANGUAGES.get(lang, {"name": lang.upper(), "flag": "🌐"})
            lang_name = lang_info["name"]
            lang_flag = lang_info.get("flag", "🌐")
            p("detecting", 1, 1, f"✅ Language: {lang_flag} {lang_name}")

        self.job_manager.update_job(job_id, detected_language={
            "code": lang, "name": lang_name, "flag": lang_flag
        })

        # 2 ── Transcribe Audio ───────────────────────────────────────────────
        p("transcribing", 0, 1, f"📝 Transcribing {lang_flag} {lang_name} audio with Whisper...")
        if translate_captions:
            transcript = transcriber.transcribe_and_translate(audio_path, lang)
        else:
            transcript = transcriber.transcribe(audio_path, lang)

        if not transcript.get("text"):
            raise ValueError("Could not transcribe audio. Try a different language or check audio quality.")

        transcribed_text = transcript.get("text", "")
        word_count = len(transcribed_text.split())
        duration = transcript.get("duration", 0)

        p("transcribing", 1, 1,
          f"✅ Transcribed: {word_count} words • {round(duration)}s")

        self.job_manager.update_job(job_id, transcript={
            "text": transcribed_text[:500],
            "language": lang,
            "word_count": word_count,
            "duration": duration
        })

        # 3 ── Analyze Transcript for B-Roll Keywords ─────────────────────────
        p("analyzing", 0, 1, "🧠 Analyzing content for B-roll search...")

        # Use english text for analysis (original or translated)
        analysis_text = transcript.get("translated_text") or transcribed_text
        analyzer = FreeScriptAnalyzer()
        analysis = analyzer.analyze(analysis_text)
        scenes = analysis.get("scenes", [])
        mood = analysis.get("mood", "inspirational")

        p("analyzing", 1, 1, f"✅ {len(scenes)} scenes • mood: {mood}")

        # 4 ── Fetch B-Roll ───────────────────────────────────────────────────
        orientation = "portrait" if any("portrait" in s for s in sizes) else "landscape"
        p("broll", 0, len(scenes), "🎬 Fetching matching B-roll footage...")
        broll_fetcher = FreeBRollFetcher()
        broll_clips = broll_fetcher.fetch_all(
            scenes, orientation=orientation,
            progress_callback=lambda **kw: p(**kw)
        )
        found = sum(1 for v in broll_clips.values() if v)
        p("broll", len(scenes), len(scenes), f"✅ B-roll: {found}/{len(scenes)} clips")

        # 5 ── Get Background Music ───────────────────────────────────────────
        music_path = None
        if add_bgm:
            p("music", 0, 1, f"🎵 Finding {mood} background music...")
            music_fetcher = FreeMusicFetcher()
            music_path = music_fetcher.get_music(mood)
            p("music", 1, 1, "✅ Music found!" if music_path else "⚠️ No music")

        # 6 ── Generate Captions ──────────────────────────────────────────────
        captions = []
        srt_path = None
        if add_captions:
            p("captions", 0, 1, "📝 Generating synced captions...")

            # Use translated text for captions if requested
            cap_source = "translated_segments" if translate_captions else "segments"
            caption_transcript = {
                "segments": transcript.get(cap_source, transcript.get("segments", [])),
                "words": transcript.get("words", [])
            }
            captions = transcriber.generate_captions(
                caption_transcript, style=caption_style_pref
            )

            # Save SRT for burning
            if captions:
                srt_path = f"static/uploads/temp/{job_id}_captions.srt"
                Path(srt_path).parent.mkdir(exist_ok=True)
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write(transcriber.to_srt(captions))

            p("captions", 1, 1, f"✅ {len(captions)} caption segments")

        # 7 ── Compose Videos ─────────────────────────────────────────────────
        composer = VideoComposer()
        editor = RawClipsEditor()
        outputs = []

        for i, size in enumerate(sizes):
            p("compose", i, len(sizes), f"🎞️ Composing {size} video...")

            compose_cfg = {
                "size": size,
                "music_volume": music_volume,
                "voice_volume": 1.0,
                "add_captions": add_captions,
                "captions_style": config.get("captions_style", {
                    "position": "bottom", "font_size": "medium",
                    "highlight_color": "#FFFF00"
                })
            }

            # Use the AUDIO as the voiceover (it IS the audio)
            out = composer.compose(
                job_id=f"{job_id}_{size}",
                analysis=analysis,
                broll_clips=broll_clips,
                voiceover_path=audio_path,   # ← use uploaded audio as VO
                music_path=music_path,
                sfx_clips={},
                captions=captions,
                config=compose_cfg,
                progress_callback=lambda **kw: p(**kw)
            )

            if out:
                outputs.append({
                    "size": size, "path": out,
                    "filename": Path(out).name,
                    "url": f"/static/outputs/{Path(out).name}"
                })
                p("compose", i+1, len(sizes), f"✅ {size} done!")

        # 8 ── Complete ───────────────────────────────────────────────────────
        if outputs:
            # Also save transcript and SRT as downloads
            transcript_path = f"static/outputs/{job_id}_transcript.txt"
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(f"Language: {lang_name} ({lang})\n")
                f.write(f"Duration: {round(duration)}s | Words: {word_count}\n\n")
                f.write("=== ORIGINAL TRANSCRIPT ===\n")
                f.write(transcribed_text + "\n")
                if translate_captions:
                    f.write("\n=== ENGLISH TRANSLATION ===\n")
                    f.write(transcript.get("translated_text", "") + "\n")

            if srt_path and Path(srt_path).exists():
                import shutil
                out_srt = f"static/outputs/{job_id}_captions.srt"
                shutil.copy2(srt_path, out_srt)
                outputs.append({
                    "size": "srt", "path": out_srt,
                    "filename": f"{job_id}_captions.srt",
                    "url": f"/static/outputs/{job_id}_captions.srt"
                })

            self.job_manager.complete_job(job_id, outputs)
            if self.socketio:
                self.socketio.emit("job_completed", {"job_id": job_id, "outputs": outputs})
        else:
            raise ValueError("No output videos generated")
