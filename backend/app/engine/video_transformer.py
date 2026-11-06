from typing import List, Dict, Any

from typing import List, Dict, Any, Optional

def build_video_filter_chain(
    raw_video_duration: float,
    target_duration: float,
    overlay_png_intervals: Optional[List[Dict[str, Any]]] = None,
    output_fps: int = 24,
    overlay_y: int = 1380,
    render_mode: str = "natural_text",
    camera_motion: str = "dynamic_zoom",
    transition_style: str = "clean_cut",
    scene_index: int = 0,
    has_subtitles: bool = False,
    subtitle_input_idx: Optional[int] = None
) -> Dict[str, Any]:
    """
    Menyusun filter_complex FFmpeg untuk video:
    1. PTS scaling & re-framing 1080x1920 9:16 + efek gerak kamera dinamis (Ken Burns / Drift).
    2. Transisi antar klip bersih tanpa kedip hitam (clean_cut) atau smooth_fade pada base video.
    3. Tempelan subtitle overlay (menggunakan single concat stream atau legacy intervals).
    """
    orig_dur = max(0.1, raw_video_duration)
    target_dur = max(0.1, target_duration)
    pts_factor = target_dur / orig_dur

    filter_chains = []

    # Konfigurasi efek gerak kamera dinamis (ringan & 10x lebih cepat dari zoompan)
    if camera_motion == "dynamic_zoom":
        # Overscan ~7% (1156x2056) dengan pergeseran kamera sinematik halus bergantian arah tiap adegan
        direction = 1 if (scene_index % 2 == 0) else -1
        scale_crop = (
            f"scale=1156:2056:force_original_aspect_ratio=increase,"
            f"crop=1080:1920:"
            f"'(iw-1080)/2 + ({direction}*16*sin(PI*t/{target_dur:.3f}))':"
            f"'(ih-1920)*(0.5 + {direction}*0.32*((t/{target_dur:.3f})-0.5))'"
        )
    elif camera_motion == "pan_drift":
        direction = 1 if (scene_index % 2 == 0) else -1
        scale_crop = (
            f"scale=1160:1960:force_original_aspect_ratio=increase,"
            f"crop=1080:1920:"
            f"'(iw-1080)*(0.5 + {direction}*0.40*((t/{target_dur:.3f})-0.5))':"
            f"'(ih-1920)/2'"
        )
    else:
        scale_crop = (
            f"scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920"
        )

    # Konfigurasi gaya transisi visual pada base video (tanpa memudarkan teks subtitle)
    if transition_style == "smooth_fade":
        fade_out_st = max(0.0, target_dur - 0.16)
        fade_part = f",fade=in:st=0:d=0.14,fade=out:st={fade_out_st:.3f}:d=0.16"
    else:
        # Clean Cut: tanpa kedip hitam antar klip, hanya polesan 0.04s di frame pertama jika klip pertama
        fade_part = ",fade=in:st=0:d=0.06" if scene_index == 0 else ""

    base_v = (
        f"[0:v]trim=0:{orig_dur:.4f},"
        f"setpts={pts_factor:.6f}*(PTS-STARTPTS),"
        f"{scale_crop},"
        f"fps={output_fps},"
        f"trim=0:{target_dur:.4f},"
        f"setpts=PTS-STARTPTS"
        f"{fade_part}[v_base]"
    )
    filter_chains.append(base_v)
    cur_v = "[v_base]"

    safe_y = max(80, min(1460, int(overlay_y or 1380)))

    # Modern High-Performance Stream Overlay (via concat demuxer stream)
    if render_mode != "clean_no_text" and has_subtitles and subtitle_input_idx is not None:
        out_v = "[v_with_sub]"
        filter_chains.append(
            f"{cur_v}[{subtitle_input_idx}:v]overlay=0:{safe_y}:eof_action=pass{out_v}"
        )
        cur_v = out_v
    elif render_mode != "clean_no_text" and overlay_png_intervals and subtitle_input_idx is None:
        # Fallback jika overlay_png_intervals dipanggil langsung tanpa concat stream
        input_args = []
        input_idx = 2
        for item in overlay_png_intervals:
            input_args.extend(["-i", item["png_path"]])
            out_v = f"[v_ov_{input_idx}]"
            t0 = max(0.0, item["start_time"])
            t1 = min(target_dur, item["end_time"])
            filter_chains.append(
                f"{cur_v}[{input_idx}:v]overlay=0:{safe_y}:enable='between(t,{t0:.3f},{t1:.3f})'{out_v}"
            )
            cur_v = out_v
            input_idx += 1
        filter_chains.append(f"{cur_v}format=yuv420p[v_out]")
        return {
            "filter_complex": ";".join(filter_chains),
            "additional_inputs": input_args,
            "output_v_tag": "[v_out]",
            "next_input_idx": input_idx
        }

    # Format yuv420p untuk kompatibilitas pemutar video (teks tetap 100% tajam dan tegas hingga akhir)
    filter_chains.append(
        f"{cur_v}format=yuv420p[v_out]"
    )

    return {
        "filter_complex": ";".join(filter_chains),
        "additional_inputs": [],
        "output_v_tag": "[v_out]",
        "next_input_idx": (subtitle_input_idx + 1) if (has_subtitles and subtitle_input_idx is not None) else 2
    }
