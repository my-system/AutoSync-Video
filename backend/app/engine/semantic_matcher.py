import re
from typing import List, Dict, Any, Tuple

# Pustaka sinonim & kata kunci semantik visual (Multilingual: ID & EN)
SEMANTIC_KEYWORDS_MAP = {
    "office": ["office", "kantor", "desk", "meja", "laptop", "computer", "pointing", "kerja", "work"],
    "city": ["city", "kota", "street", "jalan", "walking", "walk", "waving", "gedung", "trotoar"],
    "supermarket": ["supermarket", "store", "toko", "kulkas", "coffee", "kopi", "choosing", "belanja", "fridge", "market"],
    "traffic": ["traffic", "lalu lintas", "vehicles", "drive", "driving", "motor", "mobil", "jalan raya", "kendaraan", "nods"],
    "map": ["map", "peta", "sulawesi", "indonesia", "shrugs", "globe", "geografi", "daerah"],
    "studio": ["studio", "graph", "graphs", "chart", "diagram", "explains", "data", "grafik", "presentasi"],
    "closing": ["closing", "goodbye", "waves", "wave", "smiles", "penutup", "salam", "selesai", "akhir", "bye"]
}

def clean_tokens(text: str) -> List[str]:
    """Ekstraksi kata-kata unik yang sudah dibersihkan dari teks / nama berkas."""
    if not text:
        return []
    # Pecah berdasarkan spasi, underscore, dash, camelCase, angka
    subbed = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    tokens = re.findall(r'[a-zA-Z0-9]+', subbed.lower())
    # Hapus ekstensi berkas umum
    ignored = {"mp4", "mov", "avi", "mkv", "webm", "scene", "klip", "video", "clip", "character"}
    return [t for t in tokens if t not in ignored and len(t) > 1]

def calculate_semantic_score(scene_text: str, video_filename: str) -> float:
    """
    Menghitung skor kecocokan (0.0 s/d 10.0+) antara deskripsi/naskah adegan
    dengan nama berkas video menggunakan pencocokan sinonim semantik.
    """
    scene_tokens = set(clean_tokens(scene_text))
    video_tokens = set(clean_tokens(video_filename))

    score = 0.0

    # 1. Direct Token Match (Kata yang sama persis muncul)
    direct_overlap = scene_tokens.intersection(video_tokens)
    score += len(direct_overlap) * 3.0

    # 2. Semantic Synonym Match via Concept Groups
    for concept, synonyms in SEMANTIC_KEYWORDS_MAP.items():
        has_scene = any(s in scene_tokens or any(s in tok for tok in scene_tokens) for s in synonyms)
        has_video = any(s in video_tokens or any(s in tok for tok in video_tokens) for s in synonyms)

        if has_scene and has_video:
            score += 4.5

    # 3. Substring matching untuk nama yang panjang (misal 'pointing_at_office')
    for vt in video_tokens:
        for st in scene_tokens:
            if len(st) > 3 and (st in vt or vt in st):
                score += 1.5

    return score

def auto_assign_videos_to_scenes(
    scenes: List[Dict[str, Any]],
    available_videos: List[Dict[str, Any]]
) -> List[Tuple[str, Dict[str, Any], float]]:
    """
    Memetakan kumpulan video ke adegan berdasarkan skor semantik terbaik
    tanpa duplikasi (optimal greedy assignment).
    Mengembalikan list tuple: (scene_id, matched_video_dict, score)
    """
    assignments = []
    unassigned_videos = list(available_videos)

    for scene in scenes:
        scene_id = scene["id"]
        # Gabungkan judul, headline, dan naskah adegan sebagai referensi semantik
        scene_desc = f"{scene.get('title', '')} {scene.get('headline_text', '')} {scene.get('script_text', '')}"

        best_video = None
        best_score = -1.0

        for vid in unassigned_videos:
            score = calculate_semantic_score(scene_desc, vid["filename"])
            if score > best_score:
                best_score = score
                best_video = vid

        if best_video:
            assignments.append((scene_id, best_video, max(0.0, best_score)))
            unassigned_videos.remove(best_video)
        elif available_videos:
            # Fallback jika tidak ada yang cocok sama sekali
            fallback_vid = unassigned_videos.pop(0) if unassigned_videos else available_videos[0]
            assignments.append((scene_id, fallback_vid, 0.0))

    return assignments
