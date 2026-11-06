import os
import re
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List

from backend.app.database import get_db
from backend.app.models import Project, Scene, VoiceoverTrack
from backend.app.config import UPLOADS_DIR
from backend.app.engine.audio_aligner import get_media_duration, auto_segment_scenes

router = APIRouter(prefix="/uploads", tags=["uploads"])

def sanitize_name(filename: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)

def natural_sort_key(filename: str):
    """Kunci pengurutan alami (misal: klip1, klip2, klip10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', filename or '')]

@router.post("/{project_id}/voiceover")
async def upload_voiceover(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")

    clean_filename = sanitize_name(file.filename or "voiceover.mp3")
    safe_filename = f"vo_{project_id[:8]}_{clean_filename}"
    save_path = UPLOADS_DIR / safe_filename
    
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    duration = get_media_duration(str(save_path))

    vo = db.query(VoiceoverTrack).filter(VoiceoverTrack.project_id == project_id).first()
    if not vo:
        vo = VoiceoverTrack(
            project_id=project_id,
            filename=file.filename or clean_filename,
            file_path=str(save_path),
            duration_seconds=duration
        )
        db.add(vo)
    else:
        vo.filename = file.filename or clean_filename
        vo.file_path = str(save_path)
        vo.duration_seconds = duration

    db.commit()
    db.refresh(vo)

    # Sinkronkan durasi adegan jika sudah ada
    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    if scenes:
        try:
            segments = auto_segment_scenes(str(save_path), len(scenes))
            for idx, scene in enumerate(scenes):
                if idx < len(segments):
                    scene.start_time = segments[idx]["start_time"]
                    scene.end_time = segments[idx]["end_time"]
                    scene.target_duration = segments[idx]["duration"]
            db.commit()
        except Exception as e:
            print("Auto-segment error on upload:", e)

    return {
        "id": vo.id,
        "filename": vo.filename,
        "duration_seconds": vo.duration_seconds,
        "message": "Voiceover berhasil diunggah"
    }

@router.post("/{project_id}/bgm")
async def upload_bgm(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Mengunggah berkas Musik Latar (BGM) untuk proyek dengan fitur Smart Auto-Ducking."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")

    clean_filename = sanitize_name(file.filename or "bgm.mp3")
    safe_filename = f"bgm_{project_id[:8]}_{clean_filename}"
    save_path = UPLOADS_DIR / safe_filename

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    duration = get_media_duration(str(save_path))
    project.bgm_filename = file.filename or clean_filename
    project.bgm_path = str(save_path)
    if not project.bgm_volume:
        project.bgm_volume = 0.15

    db.commit()
    db.refresh(project)

    return {
        "bgm_filename": project.bgm_filename,
        "duration_seconds": duration,
        "bgm_volume": project.bgm_volume,
        "message": "Musik Latar (BGM) berhasil dipasang dengan Auto-Ducking!"
    }

@router.delete("/{project_id}/bgm")
def delete_bgm(project_id: str, db: Session = Depends(get_db)):
    """Menghapus berkas Musik Latar (BGM) dari proyek."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")

    project.bgm_filename = None
    project.bgm_path = None
    db.commit()
    return {"message": "Musik Latar (BGM) berhasil dihapus"}

@router.post("/{project_id}/videos")
async def upload_scene_videos(
    project_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")

    existing_scenes_count = db.query(Scene).filter(Scene.project_id == project_id).count()
    uploaded_scenes = []

    # Urutkan berkas secara natural berdasarkan nama file (misal klip_1, klip_2, klip_10)
    sorted_files = sorted(files, key=lambda f: natural_sort_key(f.filename or ""))

    for i, file in enumerate(sorted_files):
        order_idx = existing_scenes_count + i
        raw_name = file.filename or f"video_{order_idx+1}.mp4"
        clean_filename = sanitize_name(raw_name)
        safe_filename = f"scene_{project_id[:8]}_{order_idx+1}_{clean_filename}"
        save_path = UPLOADS_DIR / safe_filename

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        duration = get_media_duration(str(save_path))
        if duration <= 0:
            duration = 8.0

        new_scene = Scene(
            project_id=project_id,
            scene_order=order_idx,
            title=f"Adegan {order_idx + 1}",
            raw_video_filename=raw_name,
            raw_video_path=str(save_path),
            raw_video_duration=duration,
            headline_text=f"Poin {order_idx + 1}",
            script_text="",
            start_time=0.0,
            end_time=round(duration, 3),
            target_duration=round(duration, 3)
        )
        db.add(new_scene)
        uploaded_scenes.append(new_scene)

    db.commit()

    # Jika voiceover sudah ada, otomatis sinkronisasikan durasi ke jeda narasi
    if project.voiceover:
        all_scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
        try:
            segments = auto_segment_scenes(project.voiceover.file_path, len(all_scenes))
            for idx, sc in enumerate(all_scenes):
                if idx < len(segments):
                    sc.start_time = segments[idx]["start_time"]
                    sc.end_time = segments[idx]["end_time"]
                    sc.target_duration = segments[idx]["duration"]
            db.commit()
        except Exception as e:
            print("Auto-segment error on video upload:", e)

    return {"message": f"Berhasil mengunggah {len(uploaded_scenes)} video adegan"}
