"""
VideoGen AI — Free Edition
Flask app with Script Studio, Raw Clips Editor, and Audio Analyzer.
All 100% free APIs!
"""

import os
import json
import uuid
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "videogen-free-2024")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_CONTENT_LENGTH", 500)) * 1024 * 1024

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── Ensure directories exist ──────────────────────────────────────────────────
for d in ["static/outputs", "static/uploads/raw_clips",
          "static/uploads/audio_uploads", "static/uploads/broll_cache",
          "static/uploads/tts_cache", "static/uploads/music_cache",
          "static/uploads/temp", "static/uploads/transcript_cache"]:
    Path(d).mkdir(parents=True, exist_ok=True)

# ── Import managers ───────────────────────────────────────────────────────────
from utils.job_manager import JobManager
from utils.pipeline import VideoPipeline
from utils.audio_to_video_pipeline import AudioToVideoPipeline
from utils.raw_clips_editor import RawClipsEditor
from utils.free_tts import FreeTTS
from utils.video_composer import VIDEO_SIZES
from utils.multilingual_transcriber import SUPPORTED_LANGUAGES

job_manager = JobManager()
pipeline = VideoPipeline(job_manager, socketio)
audio_pipeline = AudioToVideoPipeline(job_manager, socketio)
editor = RawClipsEditor()

ALLOWED_VIDEO = {"mp4", "mov", "avi", "mkv", "webm", "m4v", "flv", "wmv", "3gp"}
ALLOWED_AUDIO = {"mp3", "wav", "m4a", "aac", "ogg", "flac", "opus", "wma"}


def allowed_file(filename, allowed_set):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_set


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/clips")
def clips_editor():
    return render_template("clips_editor.html")

@app.route("/audio")
def audio_analyzer():
    return render_template("audio_analyzer.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/settings")
def settings():
    return render_template("settings.html")


# ── Script Studio API ─────────────────────────────────────────────────────────

@app.route("/api/video/create", methods=["POST"])
def create_video():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    script = data.get("script", "").strip()
    if not script or len(script) < 10:
        return jsonify({"error": "Script too short"}), 400

    config = {
        "sizes": data.get("sizes", ["portrait_1080"]),
        "voice": {
            "provider": data.get("voice_provider", "edge_tts"),
            "voice": data.get("voice_name", "en-US-AriaNeural"),
            "speed": float(data.get("voice_speed", 1.0)),
            "lang": data.get("voice_lang", "en"),
        },
        "add_captions": data.get("add_captions", True),
        "captions_style": {
            "position": data.get("caption_position", "bottom"),
            "highlight_color": data.get("caption_color", "#FFFF00"),
            "font_size": data.get("caption_font_size", "medium")
        },
        "music_volume": float(data.get("music_volume", 0.15)),
    }
    job_id = job_manager.create_job(script, config)
    pipeline.run_in_background(job_id, script, config)
    return jsonify({"success": True, "job_id": job_id})


@app.route("/api/analyze", methods=["POST"])
def analyze_script():
    data = request.get_json()
    script = data.get("script", "").strip()
    if not script:
        return jsonify({"error": "No script"}), 400
    from utils.free_script_analyzer import FreeScriptAnalyzer
    analyzer = FreeScriptAnalyzer()
    try:
        result = analyzer.analyze(script)
        return jsonify({"success": True, "analysis": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Raw Clips Editor API ──────────────────────────────────────────────────────

@app.route("/api/clips/upload", methods=["POST"])
def upload_clips():
    """Upload raw video clips."""
    if "files" not in request.files:
        return jsonify({"error": "No files"}), 400
    files = request.files.getlist("files")
    uploaded = []
    for file in files:
        if file and allowed_file(file.filename, ALLOWED_VIDEO):
            filename = str(uuid.uuid4())[:8] + "_" + secure_filename(file.filename)
            path = f"static/uploads/raw_clips/{filename}"
            file.save(path)
            info = editor.get_video_info(path)
            uploaded.append({
                "id": str(uuid.uuid4())[:8],
                "filename": filename,
                "original_name": file.filename,
                "path": path,
                "url": f"/static/uploads/raw_clips/{filename}",
                "duration": round(info.get("duration", 0), 1),
                "width": info.get("width"),
                "height": info.get("height"),
                "size_mb": info.get("size_mb"),
                "has_audio": info.get("has_audio"),
            })
    return jsonify({"success": True, "files": uploaded})


@app.route("/api/clips/edit", methods=["POST"])
def edit_clips():
    """Start auto or manual edit job."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    clip_paths = data.get("clip_paths", [])
    if not clip_paths:
        return jsonify({"error": "No clip paths"}), 400

    # Validate paths exist
    valid_paths = [p for p in clip_paths if Path(p).exists()]
    if not valid_paths:
        return jsonify({"error": "No valid clips found"}), 400

    config = {
        "size": data.get("size", "portrait_1080"),
        "color_preset": data.get("color_preset", "cinematic"),
        "transition": data.get("transition", "fade"),
        "music_volume": float(data.get("music_volume", 0.15)),
        "max_clip_duration": float(data.get("max_clip_duration", 8.0)),
        "music_mood": data.get("music_mood", "inspirational"),
        "add_captions": data.get("add_captions", False),
        "caption_text": data.get("caption_text", ""),
        "caption_style": data.get("caption_style", {}),
        "sizes": [data.get("size", "portrait_1080")],
    }

    job_id = job_manager.create_job(f"[CLIPS EDIT] {len(valid_paths)} clips", config)

    def run_edit():
        try:
            job_manager.update_job(job_id, status="processing",
                                   message="Starting clip edit...")
            # Get music if needed
            music_path = None
            if data.get("add_music", True):
                from utils.free_broll import FreeMusicFetcher
                music_fetcher = FreeMusicFetcher()
                music_path = music_fetcher.get_music(config["music_mood"])
                config["music_path"] = music_path

            def prog(step, current, total, message):
                job_manager.update_progress(job_id, step, current, total, message)
                socketio.emit("progress", {
                    "job_id": job_id, "step": step,
                    "current": current, "total": total,
                    "message": message,
                    "progress": job_manager.get_job(job_id)["progress"]
                })

            out = editor.auto_edit(valid_paths, job_id, config,
                                   progress_callback=prog)
            if out:
                outputs = [{
                    "size": config["size"], "path": out,
                    "filename": Path(out).name,
                    "url": f"/static/outputs/{Path(out).name}"
                }]
                job_manager.complete_job(job_id, outputs)
                socketio.emit("job_completed", {"job_id": job_id, "outputs": outputs})
            else:
                job_manager.fail_job(job_id, "Edit failed — no output generated")
                socketio.emit("job_failed", {"job_id": job_id, "error": "Edit failed"})
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            job_manager.fail_job(job_id, str(e))
            socketio.emit("job_failed", {"job_id": job_id, "error": str(e)})

    import threading
    threading.Thread(target=run_edit, daemon=True).start()
    return jsonify({"success": True, "job_id": job_id})


@app.route("/api/clips/info", methods=["POST"])
def clip_info():
    data = request.get_json()
    path = data.get("path", "")
    if not path or not Path(path).exists():
        return jsonify({"error": "File not found"}), 404
    info = editor.get_video_info(path)
    return jsonify(info)


# ── Audio Analyzer API ────────────────────────────────────────────────────────

@app.route("/api/audio/upload", methods=["POST"])
def upload_audio():
    """Upload audio file."""
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files["file"]
    if not file or not allowed_file(file.filename, ALLOWED_AUDIO | ALLOWED_VIDEO):
        return jsonify({"error": "Invalid file type"}), 400

    filename = str(uuid.uuid4())[:8] + "_" + secure_filename(file.filename)
    path = f"static/uploads/audio_uploads/{filename}"
    file.save(path)

    return jsonify({
        "success": True,
        "filename": filename,
        "path": path,
        "url": f"/static/uploads/audio_uploads/{filename}",
        "size_mb": round(Path(path).stat().st_size / (1024 * 1024), 2)
    })


@app.route("/api/audio/detect-language", methods=["POST"])
def detect_language():
    """Detect language from audio file."""
    data = request.get_json()
    audio_path = data.get("path", "")
    if not audio_path or not Path(audio_path).exists():
        return jsonify({"error": "File not found"}), 404

    from utils.multilingual_transcriber import MultilingualTranscriber
    transcriber = MultilingualTranscriber()
    try:
        result = transcriber.detect_language(audio_path)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/audio/transcribe", methods=["POST"])
def transcribe_audio():
    """Transcribe audio file with Whisper."""
    data = request.get_json()
    audio_path = data.get("path", "")
    language = data.get("language")

    if not audio_path or not Path(audio_path).exists():
        return jsonify({"error": "File not found"}), 404

    from utils.multilingual_transcriber import MultilingualTranscriber
    transcriber = MultilingualTranscriber()
    try:
        transcript = transcriber.transcribe(audio_path, language=language)
        srt = transcriber.to_srt(
            transcriber.generate_captions(transcript, style="reels")
        )
        return jsonify({"success": True, "transcript": transcript, "srt": srt})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/audio/create-video", methods=["POST"])
def create_video_from_audio():
    """Create full video from audio file."""
    data = request.get_json()
    audio_path = data.get("audio_path", "")
    if not audio_path or not Path(audio_path).exists():
        return jsonify({"error": "Audio file not found"}), 404

    config = {
        "sizes": data.get("sizes", ["portrait_1080"]),
        "language": data.get("language"),
        "add_captions": data.get("add_captions", True),
        "translate": data.get("translate", False),
        "caption_style": data.get("caption_style", "reels"),
        "captions_style": {
            "position": data.get("caption_position", "bottom"),
            "highlight_color": data.get("caption_color", "#FFFF00"),
            "font_size": data.get("caption_font_size", "large"),
        },
        "add_bgm": data.get("add_bgm", True),
        "music_volume": float(data.get("music_volume", 0.12)),
    }

    job_id = job_manager.create_job(f"[AUDIO] {Path(audio_path).name}", config)
    audio_pipeline.run_in_background(job_id, audio_path, config)
    return jsonify({"success": True, "job_id": job_id})


# ── Common API ────────────────────────────────────────────────────────────────

@app.route("/api/job/<job_id>")
def get_job(job_id):
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    return jsonify({k: v for k, v in job.items() if k != "script"})


@app.route("/api/jobs")
def get_jobs():
    jobs = job_manager.get_all_jobs()
    return jsonify([{k: v for k, v in j.items() if k != "script"} for j in jobs])


@app.route("/api/job/<job_id>/delete", methods=["DELETE"])
def delete_job(job_id):
    job = job_manager.get_job(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    for output in job.get("outputs", []):
        p = Path(output.get("path", ""))
        if p.exists():
            p.unlink()
    job_manager.delete_job(job_id)
    return jsonify({"success": True})


@app.route("/api/download/<job_id>/<size>")
def download(job_id, size):
    job = job_manager.get_job(job_id)
    if not job or job["status"] != "completed":
        abort(404)
    for out in job.get("outputs", []):
        if out["size"] == size:
            p = Path(out["path"])
            if p.exists():
                ext = p.suffix
                mime = "text/plain" if ext == ".txt" else \
                       "text/srt" if ext == ".srt" else "video/mp4"
                return send_file(p, as_attachment=True,
                                 download_name=f"videogen_{job_id}_{size}{ext}",
                                 mimetype=mime)
    abort(404)


@app.route("/api/voices")
def get_voices():
    tts = FreeTTS()
    return jsonify(tts.get_all_voices())


@app.route("/api/languages")
def get_languages():
    return jsonify(SUPPORTED_LANGUAGES)


@app.route("/api/sizes")
def get_sizes():
    return jsonify(VIDEO_SIZES)


@app.route("/api/health")
def health():
    import subprocess
    ffmpeg_ok = False
    whisper_ok = False
    edge_tts_ok = False

    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        ffmpeg_ok = True
    except Exception:
        pass

    try:
        import whisper
        whisper_ok = True
    except Exception:
        pass

    try:
        import edge_tts
        edge_tts_ok = True
    except Exception:
        pass

    return jsonify({
        "status": "ok",
        "ffmpeg": ffmpeg_ok,
        "whisper": whisper_ok,
        "edge_tts": edge_tts_ok,
        "apis": {
            "pexels": bool(os.getenv("PEXELS_API_KEY")),
            "pixabay": bool(os.getenv("PIXABAY_API_KEY")),
            "freesound": bool(os.getenv("FREESOUND_API_KEY")),
        }
    })


# ── Socket.IO ─────────────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    emit("connected", {"msg": "VideoGen connected"})

@socketio.on("subscribe_job")
def on_subscribe(data):
    job_id = data.get("job_id")
    if job_id:
        job = job_manager.get_job(job_id)
        if job:
            emit("job_update", {k: v for k, v in job.items() if k != "script"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
