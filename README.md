# ⚡ AutoSync Video (Desktop Local Edition)

> **End-to-End Automated Vertical Video (9:16) & Voiceover Synchronization Engine**  
> Mengotomasi proses pascaproduksi video vertikal pendek (TikTok, Instagram Reels, YouTube Shorts) dalam 1 klik: deteksi jeda napas akustik, transkripsi per kata (Word-Level Timestamps), takarir kinetik CapCut menyala per kata, musik latar (BGM) dengan Smart Auto-Ducking, dan gerak kamera dinamis berbasis FFmpeg.

---

## 🌟 Fitur Utama

- 🎙️ **Acoustic Breath Silence Detection (`silencedetect`)**:
  - Menganalisis gelombang audio voiceover narasi dan membagi adegan otomatis di titik hening terdalam (`-35dB`) tanpa memotong pengucapan kata.
- ⚡ **Groq Whisper Large-v3 & Gemini Audio STT**:
  - Transkripsi suara super cepat (0.5 detik) dengan ekstraksi stempel waktu presisi milidetik untuk setiap kata (`word_timestamps`).
- 🔤 **Kinetic Pop-Up Karaoke Subtitles (`ffconcat` Demuxer Stream)**:
  - Kotak takarir kontras tinggi (pure white `#FFFFFF` + 8-direction black outline pada latar navy gelap).
  - Kata yang sedang diucapkan membesar secara dinamis (+10% `44px` ExtraBold) terangkat `-3px` dengan kapsul neon bercahaya (*glow accent*).
  - Menggunakan arsitektur `ffconcat 1.0` single-stream demuxer: rendering 10x lebih cepat, hemat memori, dan kebal dari limit karakter OS Windows (`[WinError 206]`).
- 🎵 **Continuous BGM & Sidechain Auto-Ducking**:
  - Musik latar mengalir bersambung tanpa jeda antar-adegan (*loop seamless*).
  - Fitur `sidechaincompress` FFmpeg otomatis menurunkan volume musik saat narator berbicara, dan menaikkannya kembali secara halus saat narator berhenti bicara.
- 🎥 **Dynamic Camera Motion & Clean Transitions**:
  - Gerakan kamera sinematik halus (*Dynamic Zoom* / *Pan Drift*) tanpa jeda frame atau lag.
  - Opsi transisi *Clean Cut* (tanpa kedip hitam) atau *Smooth Fade*.
- 📐 **Live 9:16 Subtitle Simulator**:
  - Pratinjau animasi teks karaoke kata-demi-kata secara langsung di Web UI sebelum render.
  - Pengaturan posisi vertikal teks (`overlay_y`) fleksibel dengan preset *Atas*, *Tengah*, dan *Bawah*.
- 🔒 **100% Pemrosesan Lokal & Privat**:
  - Seluruh rendering video dijalankan langsung di mesin/laptop lokal tanpa watermark dan tanpa ketergantungan server cloud eksternal.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy (SQLite), Uvicorn, Pillow (PIL), FFmpeg 7+ / 9+.
- **Frontend**: Next.js 14/16 (App Router), React, TypeScript, Tailwind CSS, Lucide Icons.
- **AI Models**: Groq Whisper-Large-v3 (Voice-to-Text), Google Gemini 2.5 Flash & Flash-Lite (Vision & Storyteller).

---

## 🚀 Panduan Instalasi & Menjalankan

### Prasyarat
1. **Python 3.10+**: Pastikan Python dan pip sudah terpasang.
2. **Node.js 18+ & npm**: Untuk menjalankan frontend studio Next.js.
3. **FFmpeg**: Terpasang di sistem dan terdaftar dalam `PATH`.

### 1. Kloning Repositori
```bash
git clone https://github.com/my-system/AutoSync-Video.git
cd AutoSync-Video
```

### 2. Setup Backend (Python Virtual Environment)
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 3. Setup Frontend
```bash
cd frontend
npm install
cd ..
```

### 4. Menjalankan Studio (1-Klik di Windows)
Cukup klik dua kali berkas:
```text
run.bat
```
Atau jalankan dari terminal PowerShell:
```powershell
.\run.bat
```

Sistem akan otomatis:
- Menyalakan **Backend API** di `http://127.0.0.1:8000` (Swagger UI: `/docs`).
- Menyalakan **Frontend Web App** di `http://localhost:3000`.
- Membuka peramban (browser) ke halaman studio.

---

## 📂 Struktur Direktori Proyek

```text
AutoSync-Video/
├── run.bat                     # Launcher 1-klik untuk Windows
├── start_backend.bat           # Launcher server FastAPI backend
├── start_frontend.bat          # Launcher Next.js frontend
├── PROJECT_SHOWCASE_MECHANISM.md # Dokumen spesifikasi mekanisme AI video generator
├── README.md                   # Dokumentasi teknis repositori
├── .gitignore
│
├── backend/                    # Backend API & Processing Engine (Python)
│   ├── app/
│   │   ├── main.py             # Inisialisasi FastAPI, CORS, & migrasi skema SQLite
│   │   ├── config.py           # Konfigurasi path storage, font, & environment
│   │   ├── database.py         # Engine database SQLite
│   │   ├── models.py           # Skema tabel Project, Scene, VoiceoverTrack, RenderJob
│   │   ├── schemas.py          # Validasi skema request/response Pydantic v2
│   │   ├── engine/             # Mesin Pemroses Video FFmpeg & Pillow
│   │   │   ├── audio_aligner.py      # Silence detection & automatic scene slicing
│   │   │   ├── audio_transcriber.py  # Groq Whisper Large-v3 & Gemini Audio STT
│   │   │   ├── subtitle_generator.py # PIL kinetic pop-up renderer & prosody alignment
│   │   │   ├── video_transformer.py  # 9:16 vertical canvas & camera motion (Dynamic Zoom)
│   │   │   ├── audio_mixer.py        # Continuous BGM & sidechaincompress auto-ducking
│   │   │   └── ffmpeg_pipeline.py    # ffconcat demuxer stream & fast concat orchestrator
│   │   └── api/                # Endpoints REST (projects, uploads, renders)
│   └── requirements.txt
│
├── frontend/                   # Web Studio UI (Next.js, TypeScript, Tailwind CSS)
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx        # Studio workspace (Timeline, Drag & Drop, Live Simulator)
│   │   │   └── layout.tsx
│   │   ├── lib/api.ts          # REST client wrapper
│   │   └── types/index.ts      # TypeScript models & schemas
│   └── package.json
│
└── storage/                    # Penyimpanan media lokal
    ├── uploads/                # Berkas audio, BGM, & video B-Roll mentah
    ├── renders/                # Berkas video MP4 1080x1920 hasil render final
    └── temp/                   # Workspace sementara klip adegan & subtitle frames
```

---

## 📄 Lisensi
Didistribusikan di bawah lisensi MIT. Silakan gunakan, modifikasi, dan kembangkan sesuai kebutuhan Anda.
