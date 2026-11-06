import threading
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import asyncio

from backend.app.database import get_db, SessionLocal
from backend.app.models import Project, Scene, RenderJob
from backend.app.schemas import RenderJobResponse, RenderTriggerRequest
from backend.app.engine.ffmpeg_pipeline import execute_render_pipeline

router = APIRouter(prefix="/renders", tags=["renders"])

def run_render_task_in_background(job_id: str, project_id: str, render_mode: str):
    """Fungsi pekerja background mandiri (laptop-friendly tanpa server Redis)."""
    db = SessionLocal()
    try:
        job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
        project = db.query(Project).filter(Project.id == project_id).first()
        if not job or not project or not project.voiceover:
            return

        job.status = "PROCESSING"
        job.progress_percent = 5
        job.current_step = "Memulai mesin render..."
        db.commit()

        scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
        scenes_data = [
            {
                "id": s.id,
                "raw_video_path": s.raw_video_path,
                "raw_video_duration": s.raw_video_duration,
                "headline_text": s.headline_text,
                "script_text": s.script_text,
                "accent_color_hex": s.accent_color_hex,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "target_duration": s.target_duration,
                "word_timestamps_json": getattr(s, "word_timestamps_json", "[]")
            }
            for s in scenes
        ]

        def on_progress(percent: int, step_msg: str):
            # Update status di database setiap ada perubahan progres
            fresh_db = SessionLocal()
            try:
                j = fresh_db.query(RenderJob).filter(RenderJob.id == job_id).first()
                if j:
                    j.progress_percent = percent
                    j.current_step = step_msg
                    fresh_db.commit()
            finally:
                fresh_db.close()

        final_path = execute_render_pipeline(
            project_id=project_id,
            job_id=job_id,
            voiceover_path=project.voiceover.file_path,
            scenes_data=scenes_data,
            render_mode=render_mode,
            output_fps=project.output_fps or 24,
            overlay_y=getattr(project, "overlay_y", 1380) or 1380,
            camera_motion=getattr(project, "camera_motion", "dynamic_zoom") or "dynamic_zoom",
            transition_style=getattr(project, "transition_style", "clean_cut") or "clean_cut",
            bgm_path=getattr(project, "bgm_path", None),
            bgm_volume=float(getattr(project, "bgm_volume", 0.15) or 0.15),
            progress_callback=on_progress
        )

        job.status = "COMPLETED"
        job.progress_percent = 100
        job.current_step = "Selesai! Video siap diunduh."
        job.output_video_path = final_path
        job.output_video_url = f"/api/v1/renders/{job_id}/stream-video"
        job.completed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        db.rollback()
        job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
        if job:
            job.status = "FAILED"
            job.error_message = str(e)
            job.current_step = f"Gagal: {str(e)[:150]}"
            db.commit()
    finally:
        db.close()

@router.post("/{project_id}", response_model=RenderJobResponse)
def trigger_render(
    project_id: str,
    req: RenderTriggerRequest,
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")

    if not project.voiceover:
        raise HTTPException(status_code=400, detail="Voiceover belum diunggah")

    scenes_count = db.query(Scene).filter(Scene.project_id == project_id).count()
    if scenes_count == 0:
        raise HTTPException(status_code=400, detail="Minimal unggah 1 klip video adegan")

    # Simpan preferensi visual/audio terbaru pada proyek jika dikirim saat trigger render
    if req.overlay_y is not None:
        project.overlay_y = req.overlay_y
    if req.camera_motion is not None:
        project.camera_motion = req.camera_motion
    if req.transition_style is not None:
        project.transition_style = req.transition_style
    if req.bgm_volume is not None:
        project.bgm_volume = req.bgm_volume

    render_job = RenderJob(
        project_id=project_id,
        render_mode=req.render_mode or "natural_text",
        status="QUEUED",
        progress_percent=0,
        current_step="Mengantre di background..."
    )
    db.add(render_job)
    db.commit()
    db.refresh(render_job)

    # Jalankan proses render di thread background lokal (hemat resource & non-blocking)
    worker_thread = threading.Thread(
        target=run_render_task_in_background,
        args=(render_job.id, project_id, render_job.render_mode),
        daemon=True
    )
    worker_thread.start()

    return render_job

@router.get("/{job_id}", response_model=RenderJobResponse)
def get_render_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Tugas render tidak ditemukan")
    return job

@router.get("/{job_id}/stream-video")
def stream_render_video(job_id: str, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse
    job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
    if not job or not job.output_video_path:
        raise HTTPException(status_code=404, detail="Video belum selesai dirender")
    return FileResponse(
        job.output_video_path,
        media_type="video/mp4",
        filename=f"autosync_{job.project_id[:6]}.mp4"
    )

@router.websocket("/ws/{job_id}")
async def websocket_render_progress(websocket: WebSocket, job_id: str):
    """Koneksi WebSocket untuk pembaruan realtime progres render ke browser."""
    await websocket.accept()
    try:
        while True:
            db = SessionLocal()
            try:
                job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
                if job:
                    await websocket.send_json({
                        "job_id": job.id,
                        "status": job.status,
                        "progress_percent": job.progress_percent,
                        "current_step": job.current_step,
                        "output_video_url": job.output_video_url,
                        "error_message": job.error_message
                    })
                    if job.status in ["COMPLETED", "FAILED"]:
                        break
            finally:
                db.close()
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
