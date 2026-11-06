import os
import subprocess
from typing import Dict, Any, Optional

def check_has_audio(file_path: str) -> bool:
    """Mengecek apakah file video memiliki track audio."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return bool(res.stdout.strip())
    except Exception:
        return False

def build_audio_filter_chain(
    raw_video_path: str,
    target_duration: float,
    pts_factor: float,
    vo_start: float = 0.0,
    vo_end: float = 0.0,
    ambient_volume: float = 0.14,
    voiceover_volume: float = 1.10,
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.15,
    bgm_input_idx: Optional[int] = None
) -> Dict[str, Any]:
    """
    Menyusun filter_complex FFmpeg untuk audio mixing:
    - Suara latar klip video (ducking ke 14% + atempo).
    - Potongan suara narator voiceover (volume 110%).
    - Background Music (BGM) kontinyu lintas adegan dengan Smart Auto-Ducking (sidechaincompress).
    """
    target_dur = max(0.1, target_duration)
    has_video_audio = check_has_audio(raw_video_path)
    has_bgm = bool(bgm_path and os.path.exists(bgm_path) and bgm_input_idx is not None)

    vo_dur = max(0.1, vo_end - vo_start) if vo_end > vo_start else target_dur
    vo_end_time = vo_start + vo_dur

    filter_chains = []

    # Voiceover segment (Input 1:a)
    # Jika BGM aktif, gandakan stream [a_vo] menjadi [a_vo_main] dan [a_vo_sc] untuk pemicu auto-ducking
    vo_base = (
        f"[1:a]atrim={vo_start:.4f}:{vo_end_time:.4f},"
        f"asetpts=PTS-STARTPTS,"
        f"apad=whole_dur={target_dur:.4f},"
        f"atrim=0:{target_dur:.4f},"
        f"volume={voiceover_volume:.2f},"
        f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    )
    if has_bgm:
        filter_chains.append(f"{vo_base},asplit=2[a_vo][a_vo_sc]")
    else:
        filter_chains.append(f"{vo_base}[a_vo]")

    mix_inputs = ["[a_vo]"]

    if has_video_audio:
        atempo = max(0.5, min(2.0, 1.0 / max(0.01, pts_factor)))
        amb_chain = (
            f"[0:a]atempo={atempo:.4f},"
            f"apad=whole_dur={target_dur:.4f},"
            f"atrim=0:{target_dur:.4f},"
            f"volume={ambient_volume:.2f},"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a_amb]"
        )
        filter_chains.append(amb_chain)
        mix_inputs.append("[a_amb]")

    if has_bgm:
        # Potong BGM sesuai rentang waktu global [vo_start, vo_end_time] agar musik mengalir nyambung antar adegan!
        # Gunakan sidechaincompress agar musik otomatis merunduk (auto-ducking) saat narator bicara
        bgm_vol_boosted = max(0.02, min(0.80, float(bgm_volume or 0.15) * 1.45))
        bgm_chain = (
            f"[{bgm_input_idx}:a]atrim={vo_start:.4f}:{vo_end_time:.4f},"
            f"asetpts=PTS-STARTPTS,"
            f"apad=whole_dur={target_dur:.4f},"
            f"atrim=0:{target_dur:.4f},"
            f"volume={bgm_vol_boosted:.3f},"
            f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a_bgm_raw];"
            f"[a_bgm_raw][a_vo_sc]sidechaincompress=threshold=0.035:ratio=4.5:attack=35:release=320[a_bgm]"
        )
        filter_chains.append(bgm_chain)
        mix_inputs.append("[a_bgm]")

    fade_out_st = max(0.0, target_dur - 0.06)
    if len(mix_inputs) > 1:
        inputs_str = "".join(mix_inputs)
        mix_chain = (
            f"{inputs_str}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0:normalize=0,"
            f"afade=in:st=0:d=0.04,afade=out:st={fade_out_st:.3f}:d=0.06[a_out]"
        )
        filter_chains.append(mix_chain)
    else:
        filter_chains.append(
            f"[a_vo]afade=in:st=0:d=0.04,afade=out:st={fade_out_st:.3f}:d=0.06[a_out]"
        )

    return {
        "filter_complex": ";".join(filter_chains),
        "output_a_tag": "[a_out]"
    }
