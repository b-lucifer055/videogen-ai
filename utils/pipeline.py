"""
VideoGen Pipeline — Free version.
Orchestrates all free components.
"""

import os
import json
import threading
from pathlib import Path

from utils.free_script_analyzer import FreeScriptAnalyzer
from utils.free_broll import FreeBRollFetcher, FreeMusicFetcher
from utils.free_tts import FreeTTS
from utils.multilingual_transcriber import MultilingualTranscriber
from utils.video_composer import VideoComposer
from utils.job_manager import JobManager


class VideoPipeline:
    def __init__(self, job_manager: JobManager, socketio=None):
        self.job_manager = job_manager
        self.socketio = socketio

    def emit(self, job_id, step, current, total, message):
        self.job_manager.update_progress(job_id, step, current, total, message)
        if self.socketio:
            job = self.job_manager.get_job(job_id)
            self.socketio.emit("progress", {
                "job_id": job_id,
                "step": step,
                "current": current,
                "total": total,
                "message": message,
                "progress": job["progress"] if job else 0
            })

    def run_in_background(self, job_id: str, script: str, config: dict):
        thread = threading.Thread(
            target=self._safe_run,
            args=(job_id, script, config),
            daemon=True
        )
        thread.start()
        return thread

    def _safe_run(self, job_id, script, config):
        try:
            self._execute(job_id, script, config)
        except Exception as e:
            import traceback
            error_msg = str(e)
            print(f"[Pipeline] ERROR {job_id}: {traceback.format_exc()}")
            self.job_manager.fail_job(job_id, error_msg)
            if self.socketio:
                self.socketio.emit("job_failed", {
                    "job_id": job_id,
                    "error": error_msg
                })

    def _execute(self, job_id, script, config):

        def p(step=None, cur=None, tot=None, msg=None,
              current=None, total=None, message=None, **kwargs):

            cur = current if current is not None else cur
            tot = total if total is not None else tot
            msg = message if message is not None else msg

            self.emit(
                job_id,
                step or "processing",
                cur if cur is not None else 0,
                tot if tot is not None else 1,
                msg or ""
            )

        sizes = config.get("sizes", ["portrait_1080"])
        voice_cfg = config.get("voice", {})
        add_captions = config.get("add_captions", True)
        music_volume = config.get("music_volume", 0.15)

        # 1 ── Analyze Script
        p("analyzing", 0, 1, "🧠 Analyzing script (free local AI)...")
        analyzer = FreeScriptAnalyzer()
        analysis = analyzer.analyze(script, voice_cfg)
        self.job_manager.update_job(job_id, analysis=analysis)

        scenes = analysis.get("scenes", [])
        p("analyzing", 1, 1, f"✅ {len(scenes)} scenes • mood: {analysis.get('mood')}")

        if not scenes:
            raise ValueError("No scenes extracted from script")

        # 2 ── Fetch B-Roll
        orientation = "portrait" if any("portrait" in s for s in sizes) else "landscape"
        p("broll", 0, len(scenes), "🎬 Searching free B-roll (Pexels/Pixabay)...")

        broll_fetcher = FreeBRollFetcher()
        broll_clips = broll_fetcher.fetch_all(
            scenes,
            orientation=orientation,
            progress_callback=lambda **kw: p(**kw)
        )

        found = sum(1 for v in broll_clips.values() if v)
        p("broll", len(scenes), len(scenes), f"✅ B-roll: {found}/{len(scenes)} clips found")

        # 3 ── Generate Voiceover
        p("voiceover", 0, 1, "🎤 Generating free voiceover (edge-tts / gTTS)...")

        tts = FreeTTS()
        voiceover_path = tts.generate(script, voice_cfg)

        if voiceover_path:
            p("voiceover", 1, 1, "✅ Voiceover generated!")
        else:
            p("voiceover", 1, 1, "⚠️ Voiceover unavailable, continuing...")

        # 4 ── Get Music
        p("music", 0, 1, "🎵 Finding free background music (Pixabay)...")

        music_fetcher = FreeMusicFetcher()
        mood = analysis.get("mood", "inspirational")
        music_path = music_fetcher.get_music(mood)

        p("music", 1, 1, "✅ Music found!" if music_path else "⚠️ Music unavailable")

        # 5 ── Get SFX
        p("sfx", 0, 1, "🔊 Fetching sound effects (Freesound)...")

        sfx_clips = {}
        for scene in scenes:
            if scene.get("sfx"):
                path = music_fetcher.get_sfx(scene["sfx"])
                sfx_clips[scene["id"]] = path

        loaded_sfx = len([v for v in sfx_clips.values() if v])
        p("sfx", 1, 1, f"✅ {loaded_sfx} SFX loaded")

        # 6 ── Generate Captions
        captions = []

        if add_captions:
            p("captions", 0, 1, "📝 Generating captions...")

            transcriber = MultilingualTranscriber()

            if voiceover_path:
                try:
                    transcript = transcriber.transcribe(voiceover_path)
                    captions = transcriber.generate_captions(transcript, style="reels")
                except Exception:
                    captions = transcriber.generate_captions(
                        {
                            "segments": [
                                {
                                    "start": s["id"] * 5,
                                    "end": s["id"] * 5 + s["duration"],
                                    "text": s["text"]
                                }
                                for s in scenes
                            ]
                        },
                        style="standard"
                    )

            p("captions", 1, 1, f"✅ {len(captions)} caption segments")

        # 7 ── Compose Videos
        composer = VideoComposer()
        outputs = []

        for i, size in enumerate(sizes):
            p("compose", i, len(sizes), f"🎞️ Composing {size}...")

            compose_cfg = {
                "size": size,
                "music_volume": music_volume,
                "voice_volume": 1.0,
                "add_captions": add_captions and ("portrait" in size or "square" in size),
                "captions_style": config.get(
                    "captions_style",
                    analysis.get("captions_style", {})
                )
            }

            out = composer.compose(
                job_id=job_id,
                analysis=analysis,
                broll_clips=broll_clips,
                voiceover_path=voiceover_path,
                music_path=music_path,
                sfx_clips=sfx_clips,
                captions=captions,
                config=compose_cfg,
                progress_callback=lambda **kw: p(**kw)
            )

            if out:
                outputs.append({
                    "size": size,
                    "path": out,
                    "filename": Path(out).name,
                    "url": f"/static/outputs/{Path(out).name}"
                })

                p("compose", i + 1, len(sizes), f"✅ {size} done!")

        # 8 ── Complete
        if outputs:
            self.job_manager.complete_job(job_id, outputs)

            if self.socketio:
                self.socketio.emit("job_completed", {
                    "job_id": job_id,
                    "outputs": outputs
                })
        else:
            raise ValueError("No output videos were generated")
