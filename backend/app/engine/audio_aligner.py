import subprocess
import json
import re
from typing import List, Dict, Any, Optional

def get_media_duration(file_path: str) -> float:
    """Mengambil durasi tepat dari file video atau audio dalam detik via ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        # Fallback ffprobe via stream duration
        cmd2 = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        res2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        val = res2.stdout.strip()
        if val and val != "N/A":
            return float(val)
        return 0.0

def detect_silences(audio_path: str, noise_db: float = -32.0, min_duration: float = 0.20) -> List[Dict[str, float]]:
    """Mendeteksi jeda hening pada audio narasi menggunakan filter silencedetect FFmpeg."""
    cmd = [
        "ffmpeg",
        "-i", audio_path,
        "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f", "null",
        "-"
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output = result.stderr

    silence_starts = []
    silence_ends = []
    
    # Ekstraksi regex untuk silence_start dan silence_end
    for line in output.splitlines():
        if "silence_start:" in line:
            match = re.search(r"silence_start:\s*([0-9.]+)", line)
            if match:
                silence_starts.append(float(match.group(1)))
        elif "silence_end:" in line:
            match = re.search(r"silence_end:\s*([0-9.]+)", line)
            if match:
                silence_ends.append(float(match.group(1)))

    silences = []
    for i in range(min(len(silence_starts), len(silence_ends))):
        start = silence_starts[i]
        end = silence_ends[i]
        mid = (start + end) / 2.0
        dur = end - start
        silences.append({
            "start": round(start, 3),
            "end": round(end, 3),
            "mid": round(mid, 3),
            "duration": round(dur, 3)
        })
    return silences

def auto_segment_scenes(audio_path: str, num_scenes: int) -> List[Dict[str, float]]:
    """Menghitung batas timestamp adegan (start, end, duration) berdasarkan jeda narasi."""
    total_dur = get_media_duration(audio_path)
    if num_scenes <= 0 or total_dur <= 0:
        return []

    if num_scenes == 1:
        return [{"scene_order": 0, "start_time": 0.0, "end_time": round(total_dur, 3), "duration": round(total_dur, 3)}]

    silences = detect_silences(audio_path, noise_db=-32.0, min_duration=0.20)
    
    # Jika silences kurang sensitif, coba threshold lebih longgar
    if len(silences) < (num_scenes - 1):
        silences = detect_silences(audio_path, noise_db=-28.0, min_duration=0.15)

    cut_points = [0.0]
    
    if len(silences) >= (num_scenes - 1):
        # Cari jeda hening yang posisinya paling mendekati pembagian proporsional
        ideal_interval = total_dur / num_scenes
        current_t = 0.0
        available_silences = list(silences)
        
        for scene_idx in range(1, num_scenes):
            target_t = scene_idx * ideal_interval
            # Pilih silence mid yang paling dekat dengan target_t dan masih > cut_points[-1] + 1.0s
            valid_candidates = [s for s in available_silences if s["mid"] > (cut_points[-1] + 1.5)]
            if valid_candidates:
                best_s = min(valid_candidates, key=lambda s: abs(s["mid"] - target_t))
                cut_points.append(best_s["mid"])
                available_silences.remove(best_s)
            else:
                cut_points.append(target_t)
    else:
        # Fallback ke pembagian waktu merata jika tidak ada jeda hening yang terdeteksi
        interval = total_dur / num_scenes
        for i in range(1, num_scenes):
            cut_points.append(round(i * interval, 3))

    cut_points.append(round(total_dur, 3))
    # Pastikan urut dan tidak duplikat
    cut_points = sorted(list(set(cut_points)))

    segments = []
    for i in range(len(cut_points) - 1):
        t0 = cut_points[i]
        t1 = cut_points[i + 1]
        segments.append({
            "scene_order": i,
            "start_time": round(t0, 3),
            "end_time": round(t1, 3),
            "duration": round(t1 - t0, 3)
        })

    return segments
