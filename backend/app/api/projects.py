import shutil
import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from backend.app.database import get_db
from backend.app.models import Project, Scene, VoiceoverTrack
from backend.app.schemas import (
    ProjectCreate, ProjectUpdate, ProjectDetailResponse, SceneBase, SceneUpdate, SceneResponse
)
from backend.app.config import UPLOADS_DIR, TEMP_DIR, GEMINI_API_KEY
from backend.app.engine.audio_aligner import auto_segment_scenes, get_media_duration
from backend.app.engine.semantic_matcher import auto_assign_videos_to_scenes
from backend.app.engine.vision_matcher import match_videos_with_gemini_vision, generate_story_from_video_frames
from backend.app.engine.audio_transcriber import transcribe_full_audio_into_scenes

router = APIRouter(prefix="/projects", tags=["projects"])

class ReorderScenesRequest(BaseModel):
    scene_ids: List[str]

class VisionMatchRequest(BaseModel):
    api_key: Optional[str] = None

class GenerateStoryRequest(BaseModel):
    topic: Optional[str] = "Edukasi Jejak Digital"
    api_key: Optional[str] = None

class TranscribeRequest(BaseModel):
    api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

@router.post("", response_model=ProjectDetailResponse)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        title=data.title,
        aspect_ratio=data.aspect_ratio or "9:16",
        output_fps=data.output_fps or 24
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@router.get("", response_model=List[ProjectDetailResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).order_by(Project.created_at.desc()).all()

@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    return project

@router.put("/{project_id}", response_model=ProjectDetailResponse)
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    
    if data.title is not None:
        project.title = data.title
    if data.aspect_ratio is not None:
        project.aspect_ratio = data.aspect_ratio
    if data.output_fps is not None:
        project.output_fps = data.output_fps
    if data.bgm_volume is not None:
        project.bgm_volume = data.bgm_volume
    if data.overlay_y is not None:
        project.overlay_y = data.overlay_y
    if data.camera_motion is not None:
        project.camera_motion = data.camera_motion
    if data.transition_style is not None:
        project.transition_style = data.transition_style
    
    db.commit()
    db.refresh(project)
    return project

@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")
    db.delete(project)
    db.commit()
    return {"message": "Proyek berhasil dihapus"}

@router.put("/{project_id}/scenes/{scene_id}", response_model=SceneResponse)
def update_scene(project_id: str, scene_id: str, data: SceneUpdate, db: Session = Depends(get_db)):
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Adegan tidak ditemukan")

    if data.scene_order is not None:
        scene.scene_order = data.scene_order
    if data.title is not None:
        scene.title = data.title
    if data.headline_text is not None:
        scene.headline_text = data.headline_text
    if data.script_text is not None:
        if data.script_text != scene.script_text:
            scene.word_timestamps_json = "[]"
        scene.script_text = data.script_text
    if data.accent_color_hex is not None:
        scene.accent_color_hex = data.accent_color_hex
    if data.start_time is not None:
        scene.start_time = data.start_time
    if data.end_time is not None:
        scene.end_time = data.end_time
    if data.target_duration is not None:
        scene.target_duration = data.target_duration
    elif (data.start_time is not None or data.end_time is not None) and scene.end_time > scene.start_time:
        scene.target_duration = round(scene.end_time - scene.start_time, 3)
    
    db.commit()
    db.refresh(scene)
    return scene

@router.post("/{project_id}/scenes/reorder")
def reorder_scenes(project_id: str, req: ReorderScenesRequest, db: Session = Depends(get_db)):
    """Memperbarui urutan sekuensial adegan berdasarkan urutan array scene_id."""
    for new_order, scene_id in enumerate(req.scene_ids):
        scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
        if scene:
            scene.scene_order = new_order
    db.commit()
    return {"message": "Urutan sekuensial adegan berhasil diperbarui"}

@router.delete("/{project_id}/scenes/{scene_id}")
def delete_scene(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    """Menghapus adegan dan mengindeks ulang sisa adegan."""
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Adegan tidak ditemukan")
    db.delete(scene)
    db.commit()

    remaining = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    for idx, s in enumerate(remaining):
        s.scene_order = idx
        s.title = f"Adegan {idx + 1}"
    db.commit()

    return {"message": "Adegan berhasil dihapus"}

@router.post("/{project_id}/scenes/{scene_id}/upload-slot")
async def upload_scene_slot_video(
    project_id: str,
    scene_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Unggah video langsung ke slot kartu adegan tertentu."""
    scene = db.query(Scene).filter(Scene.id == scene_id, Scene.project_id == project_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Adegan tidak ditemukan")

    safe_filename = f"slot_{project_id[:6]}_{scene_id[:6]}_{file.filename}"
    save_path = UPLOADS_DIR / safe_filename

    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    duration = get_media_duration(str(save_path))
    if duration <= 0:
        duration = 8.0

    scene.raw_video_filename = file.filename
    scene.raw_video_path = str(save_path)
    scene.raw_video_duration = duration
    db.commit()
    db.refresh(scene)

    return {"message": f"Klip video berhasil dipasang ke {scene.title}", "scene": scene}

@router.post("/{project_id}/generate-story")
def generate_story(
    project_id: str,
    req: GenerateStoryRequest = GenerateStoryRequest(),
    db: Session = Depends(get_db)
):
    """
    AI Storyteller: Menganalisis frame visual dari adegan-adegan yang ada
    dan secara otomatis mengisi Lencana Judul, Naskah Narasi dengan [highlight],
    serta warna aksen neon untuk setiap adegan.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")

    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    if not scenes:
        raise HTTPException(status_code=400, detail="Belum ada adegan dalam proyek ini")

    scenes_data = [
        {
            "id": s.id,
            "scene_order": s.scene_order,
            "title": s.title,
            "raw_video_path": s.raw_video_path
        }
        for s in scenes
    ]

    key_to_use = req.api_key or GEMINI_API_KEY
    if not key_to_use:
        raise HTTPException(
            status_code=400,
            detail="Gemini API Key belum dimasukkan. Silakan klik tombol 'Gemini API' di pojok kanan atas untuk memasukkan API Key Anda."
        )
    topic_to_use = req.topic or project.title or "Edukasi Jejak Digital"

    try:
        generated_list = generate_story_from_video_frames(scenes_data, key_to_use, topic_to_use)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    updated_count = 0
    # Map generated content to scenes
    for item in generated_list:
        sc_id = item.get("scene_id")
        sc = db.query(Scene).filter(Scene.id == sc_id).first()
        if sc:
            if item.get("headline_text"):
                sc.headline_text = item["headline_text"]
            if item.get("script_text"):
                sc.script_text = item["script_text"]
            if item.get("accent_color_hex"):
                sc.accent_color_hex = item["accent_color_hex"]
            updated_count += 1

    db.commit()
    return {
        "message": f"Berhasil membuat naskah & lencana otomatis untuk {updated_count} adegan dengan AI Storyteller!",
        "generated": generated_list
    }

@router.post("/{project_id}/ai-vision-match")
def perform_ai_vision_matching(
    project_id: str,
    req: VisionMatchRequest = VisionMatchRequest(),
    db: Session = Depends(get_db)
):
    """
    Mengekstrak frame dari setiap video yang diunggah dan menggunakan Gemini 3.5 Flash
    untuk menganalisis konten visual dan mencocokkannya ke naskah adegan secara otomatis.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")

    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    if not scenes:
        raise HTTPException(status_code=400, detail="Belum ada adegan dalam proyek ini")

    available_videos = []
    for s in scenes:
        if s.raw_video_path and s.raw_video_filename:
            available_videos.append({
                "filename": s.raw_video_filename,
                "path": s.raw_video_path,
                "duration": s.raw_video_duration
            })

    if not available_videos:
        raise HTTPException(status_code=400, detail="Tidak ada berkas video untuk dianalisis oleh AI Vision")

    scenes_data = [
        {
            "id": s.id,
            "title": s.title,
            "headline_text": s.headline_text or "",
            "script_text": s.script_text or ""
        }
        for s in scenes
    ]

    key_to_use = req.api_key or GEMINI_API_KEY
    if not key_to_use:
        raise HTTPException(
            status_code=400,
            detail="Gemini API Key belum dimasukkan. Silakan klik tombol 'Gemini API' di pojok kanan atas untuk memasukkan API Key Anda."
        )
    assignments = match_videos_with_gemini_vision(scenes_data, available_videos, key_to_use)

    matched_results = []
    for item in assignments:
        sc_id = item["scene_id"]
        vid = item["video"]
        reason = item.get("reason", "Cocok secara visual")

        scene = db.query(Scene).filter(Scene.id == sc_id).first()
        if scene and vid:
            scene.raw_video_filename = vid["filename"]
            scene.raw_video_path = vid["path"]
            scene.raw_video_duration = vid["duration"]
            matched_results.append({
                "scene_title": scene.title,
                "matched_video": vid["filename"],
                "reason": reason
            })

    db.commit()
    return {
        "message": f"Berhasil mencocokkan {len(matched_results)} klip secara visual dengan Gemini Vision!",
        "matches": matched_results
    }

@router.post("/{project_id}/semantic-match")
def perform_semantic_matching(project_id: str, db: Session = Depends(get_db)):
    """
    Menganalisis kata kunci naskah adegan dan nama berkas video,
    lalu memasangkan klip video yang paling sesuai ke masing-masing kartu adegan secara otomatis.
    """
    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    if not scenes:
        raise HTTPException(status_code=400, detail="Belum ada adegan dalam proyek ini")

    # Kumpulkan semua video yang tersedia di folder proyek/adegan
    available_videos = []
    for s in scenes:
        if s.raw_video_path and s.raw_video_filename:
            available_videos.append({
                "filename": s.raw_video_filename,
                "path": s.raw_video_path,
                "duration": s.raw_video_duration
            })

    if not available_videos:
        raise HTTPException(status_code=400, detail="Tidak ada berkas video untuk dicocokkan")

    scenes_data = [
        {
            "id": s.id,
            "title": s.title,
            "headline_text": s.headline_text or "",
            "script_text": s.script_text or ""
        }
        for s in scenes
    ]

    assignments = auto_assign_videos_to_scenes(scenes_data, available_videos)

    matched_results = []
    for scene_id, matched_vid, score in assignments:
        scene = db.query(Scene).filter(Scene.id == scene_id).first()
        if scene and matched_vid:
            scene.raw_video_filename = matched_vid["filename"]
            scene.raw_video_path = matched_vid["path"]
            scene.raw_video_duration = matched_vid["duration"]
            matched_results.append({
                "scene_title": scene.title,
                "matched_video": matched_vid["filename"],
                "score": round(score, 2)
            })

    db.commit()
    return {
        "message": f"Berhasil mencocokkan {len(matched_results)} klip video secara semantik!",
        "matches": matched_results
    }

@router.post("/{project_id}/load-template")
def load_digital_data_template(project_id: str, db: Session = Depends(get_db)):
    """
    Memuat template struktur 7 adegan naskah 'Jejak Digital':
    1. Kantor -> 2. Kota -> 3. Supermarket -> 4. Lalu Lintas -> 5. Sulawesi -> 6A. Studio -> 6B. Penutup
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyek tidak ditemukan")

    template_scenes = [
        {
            "order": 0,
            "title": "Adegan 1: Kantor",
            "headline": "Kamu Meninggalkan Jejak",
            "script": "Setiap hari, kita bergerak meninggalkan jejak tanpa kita sadari. / Mulai dari meja kerja, membuka [laptop], hingga ketukan jari pertama.",
            "color": "#38BDF8"
        },
        {
            "order": 1,
            "title": "Adegan 2: Kota",
            "headline": "Kota Yang Merekam",
            "script": "Saat melangkah keluar menyusuri jalanan kota yang ramai. / Kamera pengawas, sinyal ponsel, semua [terhubung] ke sistem.",
            "color": "#38BDF8"
        },
        {
            "order": 2,
            "title": "Adegan 3: Supermarket",
            "headline": "Pilihanmu Adalah Data",
            "script": "Bahkan saat memilih secangkir kopi favorit di rak kulkas. / Riwayat transaksi dan sensor toko langsung [mencatat] preferensimu.",
            "color": "#FACC15"
        },
        {
            "order": 3,
            "title": "Adegan 4: Lalu Lintas",
            "headline": "Lalu Lintas Real-Time",
            "script": "Lampu lalu lintas dan GPS kendaraan memandu jutaan orang. / Arus pergerakan ini diserap menjadi aliran [data raksasa].",
            "color": "#FB923C"
        },
        {
            "order": 4,
            "title": "Adegan 5: Sulawesi Tengah",
            "headline": "Dari Pusat Hingga Pelosok",
            "script": "Bukan hanya di kota besar, bahkan di pelosok [Sulawesi Tengah]. / Seluruh informasi geografis bermuara pada satu jaringan yang sama.",
            "color": "#4ADE80"
        },
        {
            "order": 5,
            "title": "Adegan 6A: Studio Data",
            "headline": "Grafik Kehidupan Kita",
            "script": "Data itu diolah, dianalisis, dan divisualisasikan dalam grafik. / Menjadi cermin dari setiap detik [pola hidup] modern kita.",
            "color": "#C084FC"
        },
        {
            "order": 6,
            "title": "Adegan 6B: Penutup",
            "headline": "Itu. Juga. Data.",
            "script": "Jadi, tersenyumlah. Karena setiap jejak yang kita tinggalkan... / [Itu.] [Juga.] [Data.]",
            "color": "#F43F5E"
        }
    ]

    existing_scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()

    # Perbarui adegan yang ada atau tambahkan hingga 7 adegan
    for i, t in enumerate(template_scenes):
        if i < len(existing_scenes):
            sc = existing_scenes[i]
            sc.title = t["title"]
            sc.headline_text = t["headline"]
            sc.script_text = t["script"]
            sc.accent_color_hex = t["color"]
        else:
            new_sc = Scene(
                project_id=project_id,
                scene_order=i,
                title=t["title"],
                raw_video_filename=None,
                raw_video_path=None,
                raw_video_duration=8.0,
                headline_text=t["headline"],
                script_text=t["script"],
                accent_color_hex=t["color"],
                start_time=0.0,
                end_time=8.0,
                target_duration=8.0
            )
            db.add(new_sc)

    db.commit()
    return {"message": "Template 7 Adegan Jejak Digital berhasil dimuat!"}

@router.post("/{project_id}/auto-align")
def auto_align_scenes(project_id: str, db: Session = Depends(get_db)):
    """Menganalisis audio narasi dengan deteksi jeda hening dan memetakan durasi adegan secara otomatis."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or not project.voiceover:
        raise HTTPException(status_code=400, detail="Voiceover belum diunggah untuk proyek ini")

    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    if not scenes:
        raise HTTPException(status_code=400, detail="Belum ada adegan video yang diunggah")

    segments = auto_segment_scenes(project.voiceover.file_path, len(scenes))
    
    for idx, scene in enumerate(scenes):
        if idx < len(segments):
            seg = segments[idx]
            scene.start_time = seg["start_time"]
            scene.end_time = seg["end_time"]
            scene.target_duration = seg["duration"]

    db.commit()
    return {"message": "Penyelarasan jeda suara narasi berhasil diterapkan", "segments": segments}

@router.post("/{project_id}/transcribe-voiceover")
def transcribe_project_voiceover(
    project_id: str,
    req: TranscribeRequest = TranscribeRequest(),
    db: Session = Depends(get_db)
):
    """
    Mentranskripsikan seluruh berkas voiceover ke adegan dalam 1 KALI PANGGILAN API TUNGGAL (Single Batch),
    mencegah masalah kuota 429 dan mengisi seluruh adegan sekaligus.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or not project.voiceover:
        raise HTTPException(status_code=400, detail="Voiceover belum diunggah untuk proyek ini")

    scenes = db.query(Scene).filter(Scene.project_id == project_id).order_by(Scene.scene_order).all()
    if not scenes:
        raise HTTPException(status_code=400, detail="Belum ada adegan dalam proyek ini")

    # Pastikan adegan memiliki start_time & target_duration yang selaras
    has_timing = any(s.target_duration and s.target_duration > 0.5 for s in scenes)
    if not has_timing:
        segments = auto_segment_scenes(project.voiceover.file_path, len(scenes))
        for idx, scene in enumerate(scenes):
            if idx < len(segments):
                scene.start_time = segments[idx]["start_time"]
                scene.end_time = segments[idx]["end_time"]
                scene.target_duration = segments[idx]["duration"]

    scenes_meta = [
        {
            "id": s.id,
            "scene_order": s.scene_order,
            "start_time": float(s.start_time or 0.0),
            "target_duration": float(s.target_duration or 5.0)
        }
        for s in scenes
    ]

    key_to_use = req.api_key or GEMINI_API_KEY
    if not key_to_use and not (req.groq_api_key and req.groq_api_key.startswith("gsk_")):
        raise HTTPException(
            status_code=400,
            detail="Gemini API Key atau Groq API Key belum dimasukkan. Silakan klik tombol 'Gemini API' di pojok kanan atas untuk memasukkan API Key Anda."
        )
    transcribed_scenes = transcribe_full_audio_into_scenes(
        voiceover_path=project.voiceover.file_path,
        scenes_meta=scenes_meta,
        api_key=key_to_use,
        groq_api_key=req.groq_api_key
    )

    transcribed_count = 0
    import json
    from backend.app.engine.subtitle_generator import split_into_smart_phrases, align_phrases_and_words

    for item in transcribed_scenes:
        s_idx = item.get("scene_index", 0) - 1 # 0-indexed
        if 0 <= s_idx < len(scenes):
            sc = scenes[s_idx]
            if item.get("script"):
                sc.script_text = item["script"].strip()
            if item.get("headline"):
                sc.headline_text = item["headline"].strip()

            # Simpan word-level timestamps (dari Whisper atau hasil acoustic alignment)
            raw_words = item.get("words")
            if raw_words and isinstance(raw_words, list):
                sc.word_timestamps_json = json.dumps(raw_words)
            elif sc.script_text:
                phrases = split_into_smart_phrases(sc.script_text, max_words_per_phrase=10)
                aligned = align_phrases_and_words(
                    phrases=phrases,
                    scene_duration=float(sc.target_duration or 5.0),
                    voiceover_path=project.voiceover.file_path,
                    vo_start=float(sc.start_time or 0.0)
                )
                computed_words = []
                for p in aligned:
                    for w in p.get("words", []):
                        computed_words.append({
                            "word": w["word"],
                            "start": w["start_time"],
                            "end": w["end_time"]
                        })
                sc.word_timestamps_json = json.dumps(computed_words)

            transcribed_count += 1

    db.commit()
    return {
        "message": f"Berhasil mentranskripsikan {transcribed_count} adegan langsung dari suara voiceover!",
        "transcribed_count": transcribed_count
    }
