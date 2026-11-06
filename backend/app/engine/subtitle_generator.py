import os
import re
import subprocess
from typing import List, Dict, Any, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from backend.app.config import FONT_BOLD_DEFAULT, FONT_EXTRABOLD_DEFAULT

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Mengubah kode warna HEX (#38BDF8) ke tuple RGB."""
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join([c*2 for c in hex_clean])
    if len(hex_clean) != 6:
        return (56, 189, 248) # Default cyan
    return tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))

def normalize_bracket_words(text: str) -> str:
    """
    Memecah kurung siku multi-kata seperti '[jejak digital],' menjadi '[jejak] [digital],'
    agar setiap kata terhitung 1 indeks kata yang sinkron 100% antara waktu suara dan layar.
    """
    def _repl(m):
        inner = m.group(1).strip()
        suffix = m.group(2) or ""
        parts = [p for p in inner.split() if p]
        if not parts:
            return ""
        wrapped = [f"[{p}]" for p in parts]
        wrapped[-1] = wrapped[-1] + suffix
        return " ".join(wrapped)

    return re.sub(r'\[([^\]]+)\]([.,!?:;]?)', _repl, text.strip())

def extract_spoken_words(text: str) -> List[str]:
    """
    Mengekstrak daftar kata yang diucapkan dari sebuah frasa menggunakan aturan
    tokenisasi yang 100% identik dengan wrap_tokens_to_lines.
    """
    norm = normalize_bracket_words(text)
    return [t for t in re.findall(r'(\[[^\]]+\][.,!?:;]?|\S+)', norm) if t.strip()]

def wrap_tokens_to_lines(
    text: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.ImageFont,
    max_line_width: int = 750
) -> List[List[Dict[str, Any]]]:
    """
    Memecah naskah menjadi beberapa baris yang pas (auto word-wrap),
    mempertahankan token highlight [kata] dan tanda baca tanpa memotong kata,
    serta menandai is_word=True hanya pada kata utama (bukan spasi atau tanda baca suffix).
    """
    norm_text = normalize_bracket_words(text)
    raw_tokens = re.findall(r'(\[[^\]]+\][.,!?:;]?|\S+)', norm_text)
    space_w = draw.textbbox((0, 0), ' ', font=font)[2]

    lines = []
    current_line = []
    current_w = 0

    for tok in raw_tokens:
        if tok.startswith('[') and ']' in tok:
            idx = tok.index(']')
            hl_word = tok[1:idx]
            suffix = tok[idx+1:]
            w_hl = draw.textbbox((0, 0), hl_word, font=font)[2]
            w_suf = draw.textbbox((0, 0), suffix, font=font)[2] if suffix else 0
            w_total = w_hl + w_suf

            added_w = w_total if not current_line else (space_w + w_total)
            if current_line and (current_w + added_w > max_line_width):
                lines.append(current_line)
                current_line = []
                current_w = 0
            elif current_line:
                current_line.append({'text': ' ', 'is_highlight': False, 'is_word': False, 'width': space_w})
                current_w += space_w

            current_line.append({'text': hl_word, 'is_highlight': True, 'is_word': True, 'width': w_hl})
            if suffix:
                current_line.append({'text': suffix, 'is_highlight': False, 'is_word': False, 'width': w_suf})
            current_w += w_total
        else:
            w = draw.textbbox((0, 0), tok, font=font)[2]
            added_w = w if not current_line else (space_w + w)

            if current_line and (current_w + added_w > max_line_width):
                lines.append(current_line)
                current_line = []
                current_w = 0
            elif current_line:
                current_line.append({'text': ' ', 'is_highlight': False, 'is_word': False, 'width': space_w})
                current_w += space_w

            current_line.append({'text': tok, 'is_highlight': False, 'is_word': True, 'width': w})
            current_w += w

    if current_line:
        lines.append(current_line)

    return lines

def split_into_smart_phrases(text: str, max_words_per_phrase: int = 10) -> List[str]:
    """
    Memecah teks naskah menjadi frasa-frasa pendek alami (maksimal 1-2 baris, sekitar 5-10 kata).
    Menghormati tanda henti (. ? !), koma / jeda klausa, serta menghindari kata yatim (orphan).
    """
    clean = re.sub(r'\s+', ' ', text.strip())
    if not clean:
        return []

    user_blocks = [b.strip() for b in re.split(r'[\n/]+', clean) if b.strip()]
    final_phrases = []

    for block in user_blocks:
        sentences = re.split(r'([.?!]+)', block)
        sentence_list = []
        i = 0
        while i < len(sentences):
            s = sentences[i].strip()
            punct = sentences[i+1].strip() if i+1 < len(sentences) else ''
            if s:
                sentence_list.append((s + punct).strip())
            i += 2

        for sent in sentence_list:
            words = re.findall(r'(\[[^\]]+\][.,!?:;]?|\S+)', sent)
            if not words:
                continue

            # Jika kalimat pendek (<= 10 kata), pertahankan sebagai 1 frasa (pas 1-2 baris)
            if len(words) <= max_words_per_phrase:
                final_phrases.append(' '.join(words))
                continue

            # Jika lebih dari 10 kata, pecah berdasarkan koma / jeda klausa
            comma_parts = re.split(r'([,;:]+)', sent)
            clause_list = []
            j = 0
            while j < len(comma_parts):
                c = comma_parts[j].strip()
                cp = comma_parts[j+1].strip() if j+1 < len(comma_parts) else ''
                if c:
                    clause_list.append((c + cp).strip())
                j += 2

            curr_tokens = []
            for clause in clause_list:
                c_words = re.findall(r'(\[[^\]]+\][.,!?:;]?|\S+)', clause)
                if not c_words:
                    continue

                if len(c_words) > max_words_per_phrase:
                    if curr_tokens:
                        final_phrases.append(' '.join(curr_tokens))
                        curr_tokens = []
                    half = len(c_words) // 2
                    p1 = c_words[:half]
                    p2 = c_words[half:]
                    final_phrases.append(' '.join(p1))
                    final_phrases.append(' '.join(p2))
                elif len(curr_tokens) >= 6:
                    # Jika klausa saat ini sudah cukup panjang (>= 6 kata) dan bertemu koma,
                    # jadikan frasa tersendiri agar klausa pendek berikutnya (misal "tanpa sadar,")
                    # bergabung ke kalimat lanjutan di depannya secara natural.
                    final_phrases.append(' '.join(curr_tokens))
                    curr_tokens = c_words
                elif len(curr_tokens) + len(c_words) <= max_words_per_phrase:
                    curr_tokens.extend(c_words)
                else:
                    if curr_tokens:
                        final_phrases.append(' '.join(curr_tokens))
                    curr_tokens = c_words

            if curr_tokens:
                final_phrases.append(' '.join(curr_tokens))

    return final_phrases

def render_capcut_badge_and_subtitle(
    badge_text: str,
    subtitle_text: str,
    accent_rgb: Tuple[int, int, int],
    output_png_path: str,
    active_word_index: Optional[int] = None,
    font_bold_path: str = FONT_BOLD_DEFAULT,
    font_extrabold_path: str = FONT_EXTRABOLD_DEFAULT,
    canvas_w: int = 1080,
    canvas_h: int = 560
):
    """
    Merender overlay grafis kartu teks transparan beresolusi 1080x560 piksel
    dengan pemisahan baris cerdas (auto word-wrap) dan dukungan sorot aktif kata (karaoke highlight).
    """
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        font_b = ImageFont.truetype(font_extrabold_path, 38)
    except Exception:
        font_b = ImageFont.load_default()

    try:
        font_s = ImageFont.truetype(font_bold_path, 40)
    except Exception:
        font_s = ImageFont.load_default()

    try:
        font_s_active = ImageFont.truetype(font_extrabold_path, 44)
    except Exception:
        font_s_active = font_s

    current_top = 20

    # 1. Render Headline Pill Badge (Kapsul Melengkung Bercahaya)
    by, bh = 0, 0
    has_badge = bool(badge_text and badge_text.strip())
    if has_badge:
        badge_str = badge_text.strip()
        bbox = draw.textbbox((0, 0), badge_str, font=font_b)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        pad_x, pad_y = 38, 16
        bw, bh = tw + pad_x * 2, th + pad_y * 2
        bx = (canvas_w - bw) // 2
        by = current_top

        # Efek Cahaya Neon (Soft Glow Layer)
        glow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.rounded_rectangle(
            [bx - 6, by - 6, bx + bw + 6, by + bh + 6],
            radius=bh // 2 + 6,
            fill=(*accent_rgb, 85)
        )
        glow = glow.filter(ImageFilter.GaussianBlur(12))
        img = Image.alpha_composite(img, glow)
        draw = ImageDraw.Draw(img)

        # Badan Kapsul Gelap Pekat
        draw.rounded_rectangle(
            [bx, by, bx + bw, by + bh],
            radius=bh // 2,
            fill=(8, 12, 24, 245),
            outline=(*accent_rgb, 245),
            width=3
        )

        # Teks Badge dengan Shadow Lembut
        tx = bx + pad_x - bbox[0]
        ty = by + pad_y - bbox[1]
        draw.text((tx + 2, ty + 2), badge_str, font=font_b, fill=(0, 0, 0, 220))
        draw.text((tx, ty), badge_str, font=font_b, fill=(255, 255, 255, 255))

    # 2. Render Subtitle Narasi (Takarir Dinamis dengan Auto Word-Wrap & Karaoke Highlight)
    if subtitle_text and subtitle_text.strip():
        # Pisahkan menjadi baris-baris aman (maksimal 820px agar sangat pas 1-2 baris di layar 1080px)
        wrapped_lines = wrap_tokens_to_lines(subtitle_text, draw, font_s, max_line_width=820)
        
        if wrapped_lines:
            line_height = 54
            line_gap = 8

            line_widths = [sum(t['width'] for t in l) for l in wrapped_lines]
            max_lw = max(line_widths)

            # Wadah box gelap pas dengan teks + padding aman (stabil dan konsisten)
            pad_box_x = 36
            pad_box_y = 18
            sbw = min(canvas_w - 60, max_lw + pad_box_x * 2)
            sbh = len(wrapped_lines) * line_height + max(0, len(wrapped_lines) - 1) * line_gap + pad_box_y * 2
            sbx = (canvas_w - sbw) // 2
            sby = (by + bh + 20) if has_badge else current_top

            # Gambar background box hitam pekat (97% solid, sangat tajam dan kontras tinggi di video apa pun)
            draw.rounded_rectangle(
                [sbx, sby, sbx + sbw, sby + sbh],
                radius=20,
                fill=(8, 12, 22, 248),
                outline=(255, 255, 255, 45),
                width=1
            )

            # Render setiap baris teks pas di tengah
            word_counter = 0
            cur_y = sby + pad_box_y

            for line_tokens in wrapped_lines:
                lw = sum(t['width'] for t in line_tokens)
                line_start_x = (canvas_w - lw) // 2
                cur_x = line_start_x

                for tok in line_tokens:
                    is_space = (tok['text'] == ' ')
                    is_word = tok.get('is_word', not is_space)
                    is_active = False

                    if is_word:
                        if active_word_index is not None and word_counter == active_word_index:
                            is_active = True
                        word_counter += 1

                    if is_active:
                        # KATA YANG SEDANG NYALA (Kinetic Pop-Up Scale +10%, Soft Neon Pill & Lifted -3px)
                        draw.rounded_rectangle(
                            [cur_x - 6, cur_y - 4, cur_x + tok['width'] + 6, cur_y + line_height - 5],
                            radius=10,
                            fill=(*accent_rgb, 42),
                            outline=(*accent_rgb, 190),
                            width=2
                        )
                        w_act = draw.textbbox((0, 0), tok['text'], font=font_s_active)[2]
                        pop_x = cur_x - (w_act - tok['width']) // 2
                        pop_y = cur_y - 3
                        for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3), (-2, 0), (2, 0), (0, -2), (0, 2)]:
                            draw.text((pop_x + dx, pop_y + dy), tok['text'], font=font_s_active, fill=(0, 0, 0, 255))
                        draw.text((pop_x, pop_y), tok['text'], font=font_s_active, fill=(*accent_rgb, 255))
                    elif active_word_index is None and tok.get('is_highlight'):
                        # KATA KUNCI DENGAN BRACKET [kata] HANYA DI MODE STATIS (agar tidak bentrok dengan nyala karaoke)
                        for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3), (-2, 0), (2, 0), (0, -2), (0, 2)]:
                            draw.text((cur_x + dx, cur_y + dy), tok['text'], font=font_s, fill=(0, 0, 0, 255))
                        draw.text((cur_x, cur_y), tok['text'], font=font_s, fill=(*accent_rgb, 255))
                    else:
                        # KATA BIASA (Putih Murni dengan 8-Arah Black Outline untuk Kontras Maksimal)
                        if not is_space:
                            for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                                draw.text((cur_x + dx, cur_y + dy), tok['text'], font=font_s, fill=(0, 0, 0, 255))
                        draw.text((cur_x, cur_y), tok['text'], font=font_s, fill=(255, 255, 255, 255))

                    cur_x += tok['width']

                cur_y += line_height + line_gap

    os.makedirs(os.path.dirname(output_png_path), exist_ok=True)
    img.save(output_png_path, "PNG")
    return output_png_path

def compute_word_prosody_weight(word_token: str) -> Tuple[float, float]:
    """
    Menghitung (speech_weight, pause_weight) berdasarkan suku kata Bahasa Indonesia
    (jumlah grup vokal, singkatan kapital seperti HP, kata sambung cepat) dan tanda baca jeda nafas.
    """
    clean_tok = word_token.replace('[', '').replace(']', '').strip()
    alpha_only = re.sub(r'[^a-zA-Z0-9]', '', clean_tok).lower()

    # Hitung grup vokal sebagai estimasi suku kata Bahasa Indonesia
    vowels = len(re.findall(r'[aiueo]+', alpha_only))
    if vowels == 0 and len(alpha_only) > 0:
        # Singkatan konsonan seperti 'HP', 'TV', 'PC' diucapkan per huruf (2-3 suku kata)
        vowels = len(alpha_only)

    speech_w = max(0.85, vowels * 1.15 + len(alpha_only) * 0.16)

    # Kata sambung singkat diucapkan lebih cepat dalam percakapan natural
    if alpha_only in {'di', 'ke', 'yang', 'dan', 'tak', 'itu', 'ini', 'dari', 'atau'}:
        speech_w *= 0.80

    # Jeda nafas alami setelah tanda baca (prosody pause)
    pause_w = 0.0
    if clean_tok.endswith(('.', '!', '?')):
        pause_w = 0.42
    elif clean_tok.endswith((',', ';', ':')):
        pause_w = 0.28

    return speech_w, pause_w

def detect_scene_silences(
    voiceover_path: Optional[str],
    vo_start: float,
    scene_duration: float,
    noise_db: float = -31.0,
    min_dur: float = 0.14
) -> List[Dict[str, float]]:
    """
    Mendeteksi jeda hening (nafas narator, lead-in, tail silence) di dalam potongan
    audio adegan [vo_start, vo_start + scene_duration] menggunakan FFmpeg silencedetect.
    """
    if not voiceover_path or not os.path.exists(voiceover_path):
        return []

    cmd = [
        "ffmpeg",
        "-ss", f"{max(0.0, vo_start):.4f}",
        "-t", f"{max(0.2, scene_duration):.4f}",
        "-i", voiceover_path,
        "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
        "-f", "null",
        "-"
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
        output = res.stderr
    except Exception:
        return []

    starts, ends = [], []
    for line in output.splitlines():
        if "silence_start:" in line:
            m = re.search(r"silence_start:\s*([0-9.\-]+)", line)
            if m:
                starts.append(max(0.0, float(m.group(1))))
        elif "silence_end:" in line:
            m = re.search(r"silence_end:\s*([0-9.\-]+)", line)
            if m:
                ends.append(min(scene_duration, float(m.group(1))))

    silences = []
    for i in range(min(len(starts), len(ends))):
        s0, s1 = starts[i], ends[i]
        if s1 - s0 >= min_dur * 0.8:
            silences.append({
                "start": round(s0, 3),
                "end": round(s1, 3),
                "mid": round((s0 + s1) / 2.0, 3),
                "duration": round(s1 - s0, 3)
            })
    return silences

def align_phrases_and_words(
    phrases: List[str],
    scene_duration: float,
    voiceover_path: Optional[str] = None,
    vo_start: float = 0.0,
    word_timestamps: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Menyelaraskan waktu mulai & selesai setiap frasa serta setiap kata di dalamnya
    menggunakan:
    1. True Word-Level Timestamps (jika tersedia dari Whisper / DB).
    2. Fallback cerdas: Prosody Syllable Weighting + Acoustic Silence Snapping.
    """
    # 1. Kumpulkan semua kata lintas frasa dalam adegan
    flat_words = []
    for p_idx, phrase in enumerate(phrases):
        spoken = extract_spoken_words(phrase)
        for w_idx, w_str in enumerate(spoken):
            sw, pw = compute_word_prosody_weight(w_str)
            # Tambahkan jeda mikro di akhir frasa bila belum ada tanda baca
            if w_idx == len(spoken) - 1 and pw == 0.0:
                pw = 0.14
            flat_words.append({
                "phrase_index": p_idx,
                "word_index": w_idx,
                "word": w_str,
                "clean_norm": re.sub(r'[^a-zA-Z0-9]', '', w_str).lower(),
                "speech_w": sw,
                "pause_w": pw,
                "is_phrase_end": (w_idx == len(spoken) - 1)
            })

    if not flat_words:
        return []

    # 1B. Jika ada True Word-Level Timestamps yang cocok dengan kata-kata di naskah, gunakan langsung!
    if word_timestamps and len(word_timestamps) >= max(1, int(len(flat_words) * 0.6)):
        wt_idx = 0
        matched_count = 0
        for fw in flat_words:
            target_norm = fw["clean_norm"]
            best_match = None
            for look_idx in range(wt_idx, min(len(word_timestamps), wt_idx + 4)):
                cand_norm = re.sub(r'[^a-zA-Z0-9]', '', str(word_timestamps[look_idx].get("word", ""))).lower()
                if cand_norm and (cand_norm == target_norm or cand_norm in target_norm or target_norm in cand_norm):
                    best_match = look_idx
                    break
            if best_match is not None:
                fw["wt_start"] = float(word_timestamps[best_match].get("start", 0.0))
                fw["wt_end"] = float(word_timestamps[best_match].get("end", fw["wt_start"] + 0.25))
                wt_idx = best_match + 1
                matched_count += 1

        if matched_count >= max(1, int(len(flat_words) * 0.65)):
            # Interpolasi kata yang belum punya timestamp & sambungkan jeda antar kata agar kotak tidak berkedip
            for i, fw in enumerate(flat_words):
                if "wt_start" not in fw:
                    prev_end = flat_words[i - 1]["wt_end"] if i > 0 and "wt_end" in flat_words[i - 1] else (i / len(flat_words)) * scene_duration
                    next_st = scene_duration
                    for k in range(i + 1, len(flat_words)):
                        if "wt_start" in flat_words[k]:
                            next_st = flat_words[k]["wt_start"]
                            break
                    fw["wt_start"] = prev_end
                    fw["wt_end"] = max(prev_end + 0.08, (prev_end + next_st) / 2.0)

            for i in range(len(flat_words)):
                t0 = 0.0 if i == 0 else flat_words[i]["wt_start"]
                t1 = scene_duration if i == len(flat_words) - 1 else max(t0 + 0.05, flat_words[i + 1]["wt_start"])
                flat_words[i]["start_time"] = max(0.0, min(scene_duration, t0))
                flat_words[i]["end_time"] = max(flat_words[i]["start_time"] + 0.04, min(scene_duration, t1))

            phrase_results = []
            for p_idx, phrase in enumerate(phrases):
                p_words = [w for w in flat_words if w["phrase_index"] == p_idx]
                if not p_words:
                    continue
                phrase_results.append({
                    "phrase_index": p_idx,
                    "phrase": phrase,
                    "start_time": round(p_words[0]["start_time"], 3),
                    "end_time": round(p_words[-1]["end_time"], 3),
                    "words": [
                        {
                            "word_index": w["word_index"],
                            "word": w["word"],
                            "start_time": round(w["start_time"], 3),
                            "end_time": round(w["end_time"], 3)
                        }
                        for w in p_words
                    ]
                })
            return phrase_results

    # 2. Deteksi jeda hening aktual dari gelombang audio adegan
    silences = detect_scene_silences(voiceover_path, vo_start, scene_duration)

    # Tentukan batas efektif mulai bicara (lead-in) dan selesai bicara (tail)
    speech_start = 0.0
    speech_end = scene_duration
    mid_silences = []

    for sil in silences:
        if sil["start"] <= 0.08 and sil["end"] < min(0.55, scene_duration * 0.25):
            speech_start = sil["end"]
        elif sil["end"] >= scene_duration - 0.08 and sil["start"] > max(scene_duration - 0.75, scene_duration * 0.75):
            speech_end = sil["start"]
        elif sil["start"] > speech_start + 0.25 and sil["end"] < speech_end - 0.25:
            mid_silences.append(sil)

    active_span = max(0.4, speech_end - speech_start)

    # 3. Hitung ekspektasi posisi waktu tiap kata berdasarkan bobot suku kata + jeda tanda baca
    # (Kata terakhir tidak perlu dihitung pause_w-nya di dalam active_span karena sudah ditangani speech_end)
    total_units = sum(
        w["speech_w"] + (0.0 if i == len(flat_words) - 1 else w["pause_w"] * 2.2)
        for i, w in enumerate(flat_words)
    ) or 1.0

    cum_u = 0.0
    for i, w in enumerate(flat_words):
        u_speech = w["speech_w"]
        u_pause = 0.0 if i == len(flat_words) - 1 else w["pause_w"] * 2.2
        w["exp_start"] = speech_start + (cum_u / total_units) * active_span
        cum_u += u_speech
        w["exp_speech_end"] = speech_start + (cum_u / total_units) * active_span
        cum_u += u_pause
        w["exp_end"] = speech_start + (cum_u / total_units) * active_span

    # 4. Snap (kunci) kata yang memiliki jeda tanda baca (koma/titik/akhir frasa) ke silence aktual terdekat
    # Indeks batas segmen: (word_idx_end_inclusive, audio_speech_end, next_audio_speech_start)
    anchors: List[Tuple[int, float, float]] = []
    used_word_indices = set()

    # Urutkan mid_silences berdasarkan durasi terpanjang agar jeda kalimat utama terkunci lebih dulu
    for sil in sorted(mid_silences, key=lambda x: x["duration"], reverse=True):
        best_idx = None
        best_dist = 999.0
        max_tol = max(0.85, scene_duration * 0.18)

        for i in range(len(flat_words) - 1):
            if i in used_word_indices:
                continue
            w = flat_words[i]
            # Prioritaskan kata ber-tanda baca atau kata terakhir dari suatu frasa
            if w["pause_w"] <= 0.0 and not w["is_phrase_end"]:
                continue
            dist = abs(w["exp_speech_end"] - sil["start"])
            # Beri bonus kedekatan jika kata memiliki tanda baca koma/titik eksplisit
            effective_dist = dist * (0.75 if w["pause_w"] >= 0.25 else 1.0)
            if dist <= max_tol and effective_dist < best_dist:
                # Pastikan urutan waktu tetap monotonik terhadap anchor yang sudah ada
                valid_order = True
                for a_idx, a_end, a_next in anchors:
                    if (i < a_idx and sil["end"] >= a_end) or (i > a_idx and sil["start"] <= a_next):
                        valid_order = False
                        break
                if valid_order:
                    best_dist = effective_dist
                    best_idx = i

        if best_idx is not None:
            used_word_indices.add(best_idx)
            anchors.append((best_idx, sil["start"], sil["end"]))

    anchors.sort(key=lambda x: x[0])
    # Tambahkan anchor penutup di kata terakhir
    anchors.append((len(flat_words) - 1, speech_end, scene_duration))

    # 5. Distribusikan waktu bicara di dalam setiap segmen di antara anchor akustik
    seg_start_idx = 0
    seg_start_t = speech_start

    for anchor_idx, anchor_speech_end, anchor_next_start in anchors:
        seg_words = flat_words[seg_start_idx : anchor_idx + 1]
        seg_dur = max(0.05, anchor_speech_end - seg_start_t)

        # Hitung bobot internal segmen
        seg_weights = []
        for local_i, w in enumerate(seg_words):
            # Jika bukan kata paling ujung segmen, sertakan bobot jeda tanda baca bila ada
            pw_extra = 0.0 if local_i == len(seg_words) - 1 else w["pause_w"] * 1.8
            seg_weights.append(w["speech_w"] + pw_extra)

        total_sw = sum(seg_weights) or 1.0
        cur_t = seg_start_t

        for local_i, (w, sw) in enumerate(zip(seg_words, seg_weights)):
            w_dur = (sw / total_sw) * seg_dur
            t0 = cur_t
            t1 = cur_t + w_dur if local_i < len(seg_words) - 1 else anchor_speech_end
            w["start_time"] = t0
            w["end_time"] = t1
            cur_t = t1

        # Kata terakhir pada segmen ini menahan tampilan selama jeda nafas sampai kata berikutnya mulai bicara
        flat_words[anchor_idx]["end_time"] = anchor_next_start

        seg_start_idx = anchor_idx + 1
        seg_start_t = anchor_next_start

    # Pastikan kata pertama mulai dari 0.0 agar kotak subtitle langsung tampil sejak awal adegan
    if flat_words:
        flat_words[0]["start_time"] = 0.0
        flat_words[-1]["end_time"] = scene_duration

    # 6. Kelompokkan kembali per frasa
    phrase_results = []
    for p_idx, phrase in enumerate(phrases):
        p_words = [w for w in flat_words if w["phrase_index"] == p_idx]
        if not p_words:
            continue
        phrase_results.append({
            "phrase_index": p_idx,
            "phrase": phrase,
            "start_time": round(p_words[0]["start_time"], 3),
            "end_time": round(p_words[-1]["end_time"], 3),
            "words": [
                {
                    "word_index": w["word_index"],
                    "word": w["word"],
                    "start_time": round(w["start_time"], 3),
                    "end_time": round(w["end_time"], 3)
                }
                for w in p_words
            ]
        })

    return phrase_results

def get_karaoke_word_intervals(
    phrase: str,
    phrase_start: float,
    phrase_dur: float
) -> List[Dict[str, Any]]:
    """
    Menghitung durasi natural setiap kata dalam satu frasa menggunakan bobot suku kata & tanda baca.
    """
    words = extract_spoken_words(phrase)
    if not words:
        return []

    weights = []
    for idx, w in enumerate(words):
        sw, pw = compute_word_prosody_weight(w)
        extra = 0.0 if idx == len(words) - 1 else pw * 1.8
        weights.append(sw + extra)

    total_weight = sum(weights) or 1.0
    intervals = []
    cur_t = phrase_start

    for idx, (w, wt) in enumerate(zip(words, weights)):
        w_dur = (wt / total_weight) * phrase_dur
        t_end = cur_t + w_dur if idx < len(words) - 1 else phrase_start + phrase_dur
        intervals.append({
            "word_index": idx,
            "word": w,
            "start_time": round(cur_t, 3),
            "end_time": round(t_end, 3)
        })
        cur_t = t_end

    return intervals

def generate_scene_subtitle_overlays(
    scene_id: str,
    headline_text: str,
    script_text: str,
    accent_hex: str,
    scene_duration: float,
    output_dir: str,
    karaoke_mode: bool = True,
    voiceover_path: Optional[str] = None,
    vo_start: float = 0.0,
    word_timestamps: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Membuat sequence gambar overlay dinamis dengan animasi takarir menyala per kata (karaoke kinetic typography)
    selaras dengan intonasi & jeda nafas narasi audio.
    """
    accent_rgb = hex_to_rgb(accent_hex)
    intervals = []

    clean_script = (script_text or "").strip()
    if not clean_script:
        # Jika tidak ada naskah, tampilkan badge saja
        png_path = os.path.join(output_dir, f"overlay_{scene_id}_badge.png")
        render_capcut_badge_and_subtitle(
            badge_text=headline_text,
            subtitle_text="",
            accent_rgb=accent_rgb,
            output_png_path=png_path
        )
        intervals.append({
            "png_path": png_path,
            "start_time": 0.0,
            "end_time": round(scene_duration, 3)
        })
        return intervals

    # Pecah otomatis naskah menjadi frasa-frasa pendek alami (maksimal 1-2 baris, 5-10 kata per tampilan)
    raw_parts = split_into_smart_phrases(clean_script, max_words_per_phrase=10)
    if not raw_parts:
        raw_parts = [clean_script]

    # Selaraskan waktu frasa & kata dengan gelombang suara (word_timestamps / acoustic silence snapping + syllable prosody)
    aligned_phrases = align_phrases_and_words(
        phrases=raw_parts,
        scene_duration=scene_duration,
        voiceover_path=voiceover_path,
        vo_start=vo_start,
        word_timestamps=word_timestamps
    )

    for p_item in aligned_phrases:
        p_idx = p_item["phrase_index"]
        part = p_item["phrase"]
        p_start = p_item["start_time"]
        p_end = p_item["end_time"]
        word_ints = p_item["words"]

        if karaoke_mode and scene_duration >= 1.5 and word_ints:
            # Mode Karaoke: Tiap kata menyala bergantian mengikuti intonasi & jeda suara asli
            for wi in word_ints:
                w_idx = wi["word_index"]
                png_path = os.path.join(output_dir, f"ov_{scene_id}_p{p_idx}_w{w_idx}.png")
                render_capcut_badge_and_subtitle(
                    badge_text=headline_text,
                    subtitle_text=part,
                    accent_rgb=accent_rgb,
                    output_png_path=png_path,
                    active_word_index=w_idx
                )
                intervals.append({
                    "png_path": png_path,
                    "start_time": wi["start_time"],
                    "end_time": wi["end_time"]
                })
        else:
            # Mode Statis Tradisional
            png_path = os.path.join(output_dir, f"ov_{scene_id}_p{p_idx}.png")
            render_capcut_badge_and_subtitle(
                badge_text=headline_text,
                subtitle_text=part,
                accent_rgb=accent_rgb,
                output_png_path=png_path
            )
            intervals.append({
                "png_path": png_path,
                "start_time": p_start,
                "end_time": p_end
            })

    return intervals
