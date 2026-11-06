import os
import re
import json
import base64
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

from backend.app.config import TEMP_DIR, GEMINI_API_KEY
from backend.app.models import Scene, VoiceoverTrack

def transcribe_full_audio_into_scenes(
    voiceover_path: str,
    scenes_meta: List[Dict[str, Any]],
    api_key: str = GEMINI_API_KEY,
    groq_api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Mentranskripsikan seluruh berkas voiceover dalam 1 KALI PANGGILAN API TUNGGAL (Single Batch),
    mencegah masalah kuota 429 dan menghasilkan teks naskah serta lencana judul
    untuk seluruh adegan sekaligus dengan akurasi ejaan tinggi.
    """
    if not os.path.exists(voiceover_path):
        raise FileNotFoundError(f"Berkas voiceover tidak ditemukan: {voiceover_path}")

    # 1. Jika ada Groq API Key, gunakan Groq Whisper Large v3 (Tercepat di dunia & kuota besar)
    if groq_api_key and groq_api_key.startswith("gsk_"):
        try:
            return transcribe_with_groq_whisper(voiceover_path, scenes_meta, groq_api_key)
        except Exception as e:
            print(f"Groq Whisper fallback to Gemini: {e}")

    # 2. Gunakan Gemini Multimodal Audio dalam 1 Batch Request
    with open(voiceover_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    # Susun panduan pembagian adegan berdasarkan timing
    scene_descriptions = []
    for idx, sc in enumerate(scenes_meta):
        st = sc.get("start_time", 0.0)
        dur = sc.get("target_duration", 5.0)
        scene_descriptions.append(
            f"- Adegan {idx + 1}: Detik {st:.2f} s/d {st + dur:.2f}"
        )

    prompt = (
        "Kamu adalah asisten profesional video subtitle dan voiceover synchronization bahasa Indonesia.\n"
        "Dengarkan rekaman audio voiceover ini secara utuh dan cermat.\n"
        "Audio ini dibagi menjadi beberapa adegan video pendek dengan rentang waktu:\n"
        + "\n".join(scene_descriptions) + "\n\n"
        "Tugasmu:\n"
        "1. Transkripsikan kalimat narasi yang diucapkan narator pada masing-masing adegan secara lengkap, tepat, dan alami dalam bahasa Indonesia.\n"
        "2. Buatkan 1 judul lencana (headline badge) yang sangat singkat (2-4 kata, menarik & punchy ala CapCut/TikTok) untuk setiap adegan.\n\n"
        "Keluarkan HANYA JSON murni tanpa markdown dengan format:\n"
        "{\n"
        '  "scenes": [\n'
        "    {\n"
        '      "scene_index": 1,\n'
        '      "headline": "Judul Singkat",\n'
        '      "script": "Teks kalimat narasi yang diucapkan narator pada adegan ini..."\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    models_order = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-flash-latest"
    ]

    last_error = None
    for model_name in models_order:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "audio/mp3",
                                "data": audio_b64
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json"
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=35) as res:
                res_json = json.loads(res.read().decode("utf-8"))
                text_out = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                # Bersihkan markdown fence jika ada
                if text_out.startswith("```"):
                    text_out = re.sub(r"^```[a-zA-Z]*\n", "", text_out)
                    text_out = re.sub(r"\n```$", "", text_out)
                parsed = json.loads(text_out)
                return parsed.get("scenes", [])
        except urllib.error.HTTPError as e:
            last_error = f"{model_name} HTTP {e.code}: {e.reason}"
            continue
        except Exception as e:
            last_error = f"{model_name} Error: {e}"
            continue

    raise RuntimeError(f"Gagal mentranskripsikan audio (semua model dicoba): {last_error}")

def transcribe_with_groq_whisper(
    voiceover_path: str,
    scenes_meta: List[Dict[str, Any]],
    groq_api_key: str
) -> List[Dict[str, Any]]:
    """
    Transkripsi super cepat menggunakan Groq Whisper-large-v3.
    """
    # Multipart POST ke https://api.groq.com/openai/v1/audio/transcriptions
    # Menggunakan model 'whisper-large-v3-turbo'
    boundary = "----WebKitFormBoundaryGroqWhisper"
    with open(voiceover_path, "rb") as f:
        file_bytes = f.read()

    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(voiceover_path)}"\r\n'.encode("utf-8"))
    body.extend(b"Content-Type: audio/mpeg\r\n\r\n")
    body.extend(file_bytes)
    body.extend(b"\r\n")

    fields = [
        ("model", "whisper-large-v3-turbo"),
        ("language", "id"),
        ("response_format", "verbose_json"),
        ("timestamp_granularities[]", "word"),
        ("timestamp_granularities[]", "segment")
    ]
    for k, v in fields:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{v}\r\n".encode("utf-8"))
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        }
    )

    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))
        segments = data.get("segments", [])
        all_words = data.get("words", [])
        
        # Petakan segmen & word-level timestamps Whisper ke adegan berdasarkan rentang waktu
        results = []
        for idx, sc in enumerate(scenes_meta):
            st = sc.get("start_time", 0.0)
            dur = sc.get("target_duration", 5.0)
            end = st + dur
            # Kumpulkan kata/segmen yang berada dalam rentang [st, end]
            matching_texts = []
            for seg in segments:
                seg_st = seg.get("start", 0.0)
                seg_end = seg.get("end", 0.0)
                if (seg_st >= st - 0.5 and seg_st < end) or (seg_end > st and seg_end <= end + 0.5):
                    matching_texts.append(seg.get("text", "").strip())

            scene_words = []
            for w in all_words:
                w_st = float(w.get("start", 0.0))
                w_end = float(w.get("end", w_st + 0.2))
                w_mid = (w_st + w_end) / 2.0
                if st - 0.15 <= w_mid <= end + 0.15:
                    scene_words.append({
                        "word": w.get("word", "").strip(),
                        "start": round(max(0.0, w_st - st), 3),
                        "end": round(min(dur, max(0.05, w_end - st)), 3)
                    })
            
            sc_text = " ".join(matching_texts).strip()
            headline = " ".join(re.findall(r'\b\w+\b', sc_text)[:3]).title() if sc_text else f"Poin {idx+1}"
            results.append({
                "scene_index": idx + 1,
                "headline": headline,
                "script": sc_text,
                "words": scene_words
            })
        return results
