"""
Job Manager - Manages video generation jobs, their status, and results.
Uses a simple JSON file-based queue (can be upgraded to Redis/Celery).
"""

import os
import json
import time
import uuid
import threading
from pathlib import Path
from datetime import datetime


JOBS_FILE = Path("static/jobs.json")


class JobManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._load_jobs()

    def _load_jobs(self):
        if JOBS_FILE.exists():
            try:
                with open(JOBS_FILE, "r") as f:
                    self._jobs = json.load(f)
            except Exception:
                self._jobs = {}
        else:
            self._jobs = {}

    def _save_jobs(self):
        with open(JOBS_FILE, "w") as f:
            json.dump(self._jobs, f, indent=2)

    def create_job(self, script: str, config: dict) -> str:
        """Create a new video generation job. Returns job_id."""
        job_id = str(uuid.uuid4())[:12]
        with self._lock:
            self._jobs[job_id] = {
                "id": job_id,
                "status": "queued",
                "progress": 0,
                "current_step": "queued",
                "message": "Job queued, starting soon...",
                "script": script[:500] + "..." if len(script) > 500 else script,
                "config": config,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "outputs": [],
                "analysis": None,
                "error": None,
                "logs": []
            }
            self._save_jobs()
        return job_id

    def update_job(self, job_id: str, **kwargs):
        """Update job fields."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(kwargs)
                self._jobs[job_id]["updated_at"] = datetime.now().isoformat()
                if "message" in kwargs:
                    self._jobs[job_id]["logs"].append({
                        "time": datetime.now().isoformat(),
                        "message": kwargs["message"]
                    })
                self._save_jobs()

    def update_progress(self, job_id: str, step: str, current: int,
                         total: int, message: str):
        """Update job progress during video generation."""
        STEP_WEIGHTS = {
            "analyzing": (0, 10),
            "broll": (10, 35),
            "voiceover": (35, 50),
            "sfx": (50, 60),
            "music": (60, 65),
            "captions": (65, 70),
            "compose": (70, 95),
            "finalizing": (95, 100),
        }

        start_pct, end_pct = STEP_WEIGHTS.get(step, (0, 100))
        if total > 0:
            step_progress = current / total
        else:
            step_progress = 0

        overall = int(start_pct + (end_pct - start_pct) * step_progress)

        self.update_job(job_id,
                        progress=overall,
                        current_step=step,
                        message=message,
                        status="processing")

    def get_job(self, job_id: str) -> dict | None:
        with self._lock:
            self._load_jobs()
            return self._jobs.get(job_id)

    def get_all_jobs(self) -> list:
        with self._lock:
            self._load_jobs()
            return sorted(
                self._jobs.values(),
                key=lambda j: j["created_at"],
                reverse=True
            )[:20]

    def complete_job(self, job_id: str, outputs: list):
        """Mark job as completed with output file paths."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "completed"
                self._jobs[job_id]["progress"] = 100
                self._jobs[job_id]["outputs"] = outputs
                self._jobs[job_id]["message"] = "Video ready for download!"
                self._jobs[job_id]["completed_at"] = datetime.now().isoformat()
                self._save_jobs()

    def fail_job(self, job_id: str, error: str):
        """Mark job as failed."""
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "failed"
                self._jobs[job_id]["error"] = error
                self._jobs[job_id]["message"] = f"Error: {error}"
                self._save_jobs()

    def delete_job(self, job_id: str):
        """Delete a job."""
        with self._lock:
            self._jobs.pop(job_id, None)
            self._save_jobs()
