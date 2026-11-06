import os
import re
import json
import base64
import urllib.request
import subprocess
from typing import List, Dict, Any, Tuple

from backend.app.config import TEMP_DIR
from backend.app.engine.audio_aligner import get_media_duration
from backend.app.engine.semantic_matcher import auto_assign_videos_to_scenes

def extract_video_frame(video_path: str, output_jpg: str, at_time: float = 2.0) -> bool:
    """Mengekstrak 1 frame representatif berukuran ringkas (maks 640px) dari berkas video menggunakan FFmpeg."""
    dur = get_media_duration(video_path)
    target_t = max(0.5, min(dur * 0.4, at_time))

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{target_t:.2f}",
        "-i", video_path,
        "-vf", "scale='min(640,iw)':-2",
        "-vframes", "1",
        "-q:v", "5",
        output_jpg
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.returncode == 0 and os.path.exists(output_jpg)

def match_videos_with_gemini_vision(
    scenes: List[Dict[str, Any]],
    available_videos: List[Dict[str, Any]],
    api_key: str
) -> List[Dict[str, Any]]:
    """
    Mengirimkan frame visual terkompresi dari setiap video ke Gemini Vision bersama naskah adegan
    untuk mencocokkan video ke adegan secara otomatis dan cerdas (Vision Multimodal).
    """
    if not api_key:
        raise ValueError("Gemini API Key tidak boleh kosong")

    temp_frames_dir = TEMP_DIR / "vision_frames"
    temp_frames_dir.mkdir(parents=True, exist_ok=True)

    video_frames = []
    for vid in available_videos:
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', vid["filename"])
        frame_path = str(temp_frames_dir / f"frame_{safe_name}.jpg")
        if extract_video_frame(vid["path"], frame_path):
            video_frames.append({
                "filename": vid["filename"],
                "path": vid["path"],
                "duration": vid["duration"],
                "frame_path": frame_path
            })

    if not video_frames:
        raise RuntimeError("Gagal mengekstrak frame dari video untuk dianalisis oleh AI Vision")

    scenes_text = "\n".join([
        f"- Adegan #{idx+1} (ID: {s['id']}):\n  Judul: {s.get('headline_text') or s.get('title', '')}\n  Naskah: \"{s.get('script_text', '')}\""
        for idx, s in enumerate(scenes)
    ])

    prompt = (
        "Anda adalah Senior Video Director dan Editor AI untuk video pendek TikTok/Reels.\n"
        "Berikut adalah urutan adegan naskah video pendek yang memiliki alur cerita logis berurutan:\n\n"
        f"{scenes_text}\n\n"
        f"Saya melampirkan {len(video_frames)} gambar cuplikan visual (frame) dari klip-klip video B-Roll yang diunggah pengguna.\n"
        "TUGAS UTAMA:\n"
        "Analisis hubungan tematis dan metaforis antara visual gambar, nama berkas video, dan naskah cerita:\n"
        "- Hubungkan objek visual (seperti HP, komputer, jalanan, rak toko, server center, grafik data, perisai/keamanan) "
        "dengan pesan di kalimat naskah yang paling pas.\n"
        "- Perhatikan alur kronologis cerita (misal: pembuka cerita, pembahasan inti, pusat teknologi, hingga solusi penutup/keamanan).\n"
        "- Setiap adegan HARUS mendapatkan 1 video unik (1-to-1 matching, tidak boleh ada video terduplikasi).\n\n"
        "Kembalikan HANYA JSON murni tanpa markdown dengan format:\n"
        "[\n"
        '  {"scene_id": "...", "video_filename": "...", "alasan": "..."}\n'
        "]"
    )

    parts: List[Dict[str, Any]] = [{"text": prompt}]

    for idx, vf in enumerate(video_frames):
        with open(vf["frame_path"], "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        parts.append({"text": f"Video #{idx+1} (Nama file: {vf['filename']})"})
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": b64_data
            }
        })

    models_order = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-flash-latest"
    ]

    last_err = None
    for model_name in models_order:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = json.dumps({
            "contents": [{"parts": parts}],
            "generationConfig": {"response_mime_type": "application/json"}
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()

            cleaned_json = re.sub(r"^```json\s*", "", raw_text, flags=re.MULTILINE)
            cleaned_json = re.sub(r"```$", "", cleaned_json, flags=re.MULTILINE).strip()
            matched_array = json.loads(cleaned_json)

            video_lookup = {vf["filename"]: vf for vf in video_frames}
            final_assignments = []

            for item in matched_array:
                sc_id = item.get("scene_id")
                v_name = item.get("video_filename")
                if sc_id and v_name and v_name in video_lookup:
                    final_assignments.append({
                        "scene_id": sc_id,
                        "video": video_lookup[v_name],
                        "reason": item.get("alasan", "Kecocokan visual AI")
                    })

            if len(final_assignments) >= len(scenes) * 0.7:
                return final_assignments

        except Exception as e:
            last_err = f"{model_name}: {e}"
            continue

    print("Gemini Vision fallback to semantic order due to:", last_err)
    semantic_assignments = auto_assign_videos_to_scenes(scenes, available_videos)
    fallback = []
    for s_id, vid, score in semantic_assignments:
        fallback.append({
            "scene_id": s_id,
            "video": vid,
            "reason": f"Pencocokan Semantik Urutan ({score} poin)"
        })
    return fallback

def generate_story_from_video_frames(
    scenes: List[Dict[str, Any]],
    api_key: str,
    topic: str = "Edukasi Jejak Digital"
) -> List[Dict[str, Any]]:
    """
    AI Storyteller: Menganalisis frame visual dari adegan-adegan yang ada
    dan secara otomatis merumuskan Lencana Judul (CapCut Headline), Naskah Narasi dengan [highlight],
    serta warna aksen neon untuk setiap adegan.
    """
    if not api_key:
        raise ValueError("Gemini API Key tidak boleh kosong")

    temp_frames_dir = TEMP_DIR / "vision_frames"
    temp_frames_dir.mkdir(parents=True, exist_ok=True)

    valid_scenes = []
    for s in scenes:
        if s.get("raw_video_path") and os.path.exists(s["raw_video_path"]):
            safe_id = re.sub(r'[^a-zA-Z0-9_.-]', '_', s["id"])
            frame_path = str(temp_frames_dir / f"story_frame_{safe_id}.jpg")
            if extract_video_frame(s["raw_video_path"], frame_path):
                valid_scenes.append({
                    "id": s["id"],
                    "order": s.get("scene_order", 0),
                    "title": s.get("title", ""),
                    "frame_path": frame_path
                })

    if not valid_scenes:
        raise RuntimeError("Belum ada video yang diunggah untuk dianalisis oleh AI Storyteller")

    topic_instruction = f"Topik/Tema video: '{topic}'" if topic else "Tentukan topik video terbaik berdasarkan cuplikan visual"

    prompt = (
        "Anda adalah Content Creator & Copywriter spesialis video pendek viral (Reels/TikTok/Shorts).\n"
        f"{topic_instruction}\n\n"
        f"Berikut saya lampirkan {len(valid_scenes)} gambar cuplikan frame dari adegan-adegan video berurutan.\n"
        "Untuk SETIAP adegan secara berurutan, buatkan:\n"
        "1. headline_text: Lencana judul gaya CapCut (singkat 3-5 kata, clicky/hooking, HURUF KAPITAL)\n"
        "2. script_text: Naskah narasi pendek (1-2 kalimat mengalir). Gunakan [kata] untuk menandai 1-2 kata penting yang diberi efek neon highlight\n"
        "3. accent_color_hex: Kode warna neon hex (#38BDF8 untuk cyan, #FACC15 untuk kuning, #FB923C untuk oranye, #4ADE80 untuk hijau, #C084FC untuk ungu, #F43F5E untuk merah)\n\n"
        "Kembalikan HANYA JSON array murni tanpa markdown triple backticks (```json):\n"
        "[\n"
        '  {"scene_id": "...", "headline_text": "...", "script_text": "...", "accent_color_hex": "#..."}\n'
        "]"
    )

    parts: List[Dict[str, Any]] = [{"text": prompt}]

    for idx, sc in enumerate(valid_scenes):
        with open(sc["frame_path"], "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        parts.append({"text": f"Adegan #{idx+1} (ID: {sc['id']})"})
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": b64_data
            }
        })

    models_order = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-flash-latest"
    ]

    last_err = None
    for model_name in models_order:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = json.dumps({"contents": [{"parts": parts}]}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()

            cleaned_json = re.sub(r"^```json\s*", "", raw_text, flags=re.MULTILINE)
            cleaned_json = re.sub(r"```$", "", cleaned_json, flags=re.MULTILINE).strip()
            return json.loads(cleaned_json)
        except Exception as e:
            last_err = f"{model_name}: {e}"
            continue

    raise RuntimeError(f"Gagal memproses dengan Gemini AI Storyteller: {last_err}")
