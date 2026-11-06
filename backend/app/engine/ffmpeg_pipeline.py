import os
import json
import subprocess
import shutil
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime

from backend.app.config import TEMP_DIR, RENDERS_DIR
from backend.app.engine.subtitle_generator import generate_scene_subtitle_overlays
from backend.app.engine.video_transformer import build_video_filter_chain
from backend.app.engine.audio_mixer import build_audio_filter_chain
from backend.app.engine.audio_aligner import get_media_duration

def build_subtitle_concat_file(
    overlay_intervals: List[Dict[str, Any]],
    target_duration: float,
    job_temp_dir: str,
    scene_index: int
) -> Optional[str]:
    """
    Membuat skrip ffconcat untuk stream takarir subtitle.
    Menggunakan 1 input stream FFmpeg terpadu sehingga kebal terhadap batas panjang karakter Windows ([WinError 206])
    serta merender 10x lebih cepat dan hemat memori.
    """
    if not overlay_intervals:
        return None

    transparent_png = os.path.join(job_temp_dir, "transparent_sub_dummy.png")
    if not os.path.exists(transparent_png):
        from PIL import Image
        img = Image.new("RGBA", (1080, 560), (0, 0, 0, 0))
        img.save(transparent_png)

    concat_file_path = os.path.join(job_temp_dir, f"sub_concat_{scene_index}.txt")
    trans_p = transparent_png.replace("\\", "/")

    with open(concat_file_path, "w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        cur_t = 0.0
        last_file_path = None
        for item in overlay_intervals:
            t0 = item["start_time"]
            t1 = item["end_time"]
            if t0 > cur_t + 0.01:
                gap_dur = t0 - cur_t
                f.write(f"file '{trans_p}'\n")
                f.write(f"duration {gap_dur:.4f}\n")
                cur_t = t0

            dur = max(0.04, t1 - t0)
            p_str = os.path.abspath(item["png_path"]).replace("\\", "/")
            f.write(f"file '{p_str}'\n")
            f.write(f"duration {dur:.4f}\n")
            cur_t = t1
            last_file_path = p_str

        if cur_t < target_duration - 0.01:
            gap_dur = target_duration - cur_t
            f.write(f"file '{trans_p}'\n")
            f.write(f"duration {gap_dur:.4f}\n")
            cur_t = target_duration
            last_file_path = trans_p

        if last_file_path:
            f.write(f"file '{last_file_path}'\n")

    return concat_file_path

def render_scene_clip(
    raw_video_path: str,
    voiceover_path: str,
    target_duration: float,
    vo_start: float,
    vo_end: float,
    overlay_intervals: List[Dict[str, Any]],
    output_clip_path: str,
    output_fps: int = 24,
    render_mode: str = "natural_text",
    overlay_y: int = 1380,
    camera_motion: str = "dynamic_zoom",
    transition_style: str = "clean_cut",
    scene_index: int = 0,
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.15,
    temp_dir: Optional[str] = None
):
    """Merender satu klip adegan tersinkronisasi lengkap dengan overlay, gerak kamera, dan audio mixing (+BGM auto-ducking)."""
    raw_dur = get_media_duration(raw_video_path)
    if raw_dur <= 0.1:
        raw_dur = 8.0 # Fallback jika durasi tidak terbaca

    pts_factor = target_duration / raw_dur
    work_temp_dir = temp_dir or os.path.dirname(output_clip_path)

    # Buat concat stream untuk takarir subtitle (1 input stream saja, tanpa batasan panjang karakter di Windows)
    has_sub = render_mode != "clean_no_text" and bool(overlay_intervals)
    sub_concat_file = build_subtitle_concat_file(overlay_intervals, target_duration, work_temp_dir, scene_index) if has_sub else None

    input_args = ["-i", raw_video_path, "-i", voiceover_path]
    subtitle_input_idx = None
    next_input_idx = 2

    if sub_concat_file and os.path.exists(sub_concat_file):
        input_args.extend(["-f", "concat", "-safe", "0", "-i", sub_concat_file])
        subtitle_input_idx = next_input_idx
        next_input_idx += 1

    has_bgm = bool(bgm_path and os.path.exists(bgm_path))
    bgm_input_idx = None
    if has_bgm:
        bgm_input_idx = next_input_idx
        next_input_idx += 1
        input_args.extend(["-stream_loop", "-1", "-i", bgm_path])

    v_filter_info = build_video_filter_chain(
        raw_video_duration=raw_dur,
        target_duration=target_duration,
        has_subtitles=bool(subtitle_input_idx is not None),
        subtitle_input_idx=subtitle_input_idx,
        output_fps=output_fps,
        overlay_y=overlay_y,
        render_mode=render_mode,
        camera_motion=camera_motion,
        transition_style=transition_style,
        scene_index=scene_index
    )

    a_filter_info = build_audio_filter_chain(
        raw_video_path=raw_video_path,
        target_duration=target_duration,
        pts_factor=pts_factor,
        vo_start=vo_start,
        vo_end=vo_end,
        bgm_path=bgm_path,
        bgm_volume=bgm_volume,
        bgm_input_idx=bgm_input_idx
    )

    combined_filter = f"{v_filter_info['filter_complex']};{a_filter_info['filter_complex']}"

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", combined_filter,
        "-map", v_filter_info["output_v_tag"],
        "-map", a_filter_info["output_a_tag"],
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-t", f"{target_duration:.4f}",
        output_clip_path
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg error saat render scene:\n{res.stderr[-800:]}")

def concat_scene_clips(clip_paths: List[str], output_final_path: str):
    """Menggabungkan klip-klip adegan menggunakan demuxer concat FFmpeg tanpa re-encoding (cepat)."""
    concat_txt_path = TEMP_DIR / f"concat_{os.path.basename(output_final_path)}.txt"
    with open(concat_txt_path, "w", encoding="utf-8") as f:
        for p in clip_paths:
            # Gunakan format forward slash untuk kompatibilitas FFmpeg di Windows
            safe_p = str(p).replace("\\", "/")
            f.write(f"file '{safe_p}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_txt_path),
        "-c", "copy",
        "-movflags", "+faststart",
        output_final_path
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Hapus file txt concat sementara
    if concat_txt_path.exists():
        concat_txt_path.unlink()

    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg error saat penggabungan akhir:\n{res.stderr[-800:]}")

def execute_render_pipeline(
    project_id: str,
    job_id: str,
    voiceover_path: str,
    scenes_data: List[Dict[str, Any]],
    render_mode: str = "natural_text",
    output_fps: int = 24,
    overlay_y: int = 1380,
    camera_motion: str = "dynamic_zoom",
    transition_style: str = "clean_cut",
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.15,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> str:
    """
    Eksekutor orkestrasi pemrosesan video lengkap end-to-end.
    """
    job_temp_dir = TEMP_DIR / job_id
    job_temp_dir.mkdir(parents=True, exist_ok=True)

    final_output_filename = f"autosync_{project_id[:8]}_{job_id[:8]}.mp4"
    final_output_path = RENDERS_DIR / final_output_filename

    rendered_clips = []
    total_scenes = len(scenes_data)

    try:
        if progress_callback:
            progress_callback(10, "Mempersiapkan aset dan konfigurasi render...")

        # 1. Render setiap klip adegan
        for idx, scene in enumerate(scenes_data):
            scene_id = scene.get("id", f"scene_{idx}")
            raw_vid = scene["raw_video_path"]
            target_dur = max(0.5, float(scene.get("target_duration") or 5.0))
            vo_start = float(scene.get("start_time") or 0.0)
            vo_end = float(scene.get("end_time") or (vo_start + target_dur))

            # Progress bertahap dari 15% hingga 85%
            pct = 15 + int((idx / max(1, total_scenes)) * 70)
            if progress_callback:
                progress_callback(pct, f"Merender Adegan {idx + 1} dari {total_scenes}...")

            # Parse word_timestamps_json bila ada
            word_ts = None
            raw_wt = scene.get("word_timestamps_json")
            if raw_wt:
                try:
                    parsed_wt = json.loads(raw_wt) if isinstance(raw_wt, str) else raw_wt
                    if isinstance(parsed_wt, list) and len(parsed_wt) > 0:
                        word_ts = parsed_wt
                except Exception:
                    word_ts = None

            # Buat overlay grafis CapCut tersinkronisasi gelombang audio + word timestamps
            overlay_intervals = []
            if render_mode != "clean_no_text":
                overlay_intervals = generate_scene_subtitle_overlays(
                    scene_id=scene_id,
                    headline_text=scene.get("headline_text") or "",
                    script_text=scene.get("script_text") or "",
                    accent_hex=scene.get("accent_color_hex") or "#38BDF8",
                    scene_duration=target_dur,
                    output_dir=str(job_temp_dir),
                    voiceover_path=voiceover_path,
                    vo_start=vo_start,
                    word_timestamps=word_ts
                )

            scene_clip_path = str(job_temp_dir / f"clip_{idx:03d}_{scene_id}.mp4")
            render_scene_clip(
                raw_video_path=raw_vid,
                voiceover_path=voiceover_path,
                target_duration=target_dur,
                vo_start=vo_start,
                vo_end=vo_end,
                overlay_intervals=overlay_intervals,
                output_clip_path=scene_clip_path,
                output_fps=output_fps,
                render_mode=render_mode,
                overlay_y=overlay_y,
                camera_motion=camera_motion,
                transition_style=transition_style,
                scene_index=idx,
                bgm_path=bgm_path,
                bgm_volume=bgm_volume,
                temp_dir=str(job_temp_dir)
            )
            rendered_clips.append(scene_clip_path)

        # 2. Penggabungan Cepat (Fast Concat)
        if progress_callback:
            progress_callback(90, "Menggabungkan semua adegan & optimasi faststart...")

        concat_scene_clips(rendered_clips, str(final_output_path))

        if progress_callback:
            progress_callback(100, "Render selesai! Video siap diputar.")

        return str(final_output_path)

    finally:
        # Bersihkan folder temp job setelah selesai
        shutil.rmtree(job_temp_dir, ignore_errors=True)
