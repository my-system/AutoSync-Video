import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
RENDERS_DIR = STORAGE_DIR / "renders"
TEMP_DIR = STORAGE_DIR / "temp"

# Ensure directories exist
for directory in [STORAGE_DIR, UPLOADS_DIR, RENDERS_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{BASE_DIR / 'autosync.db'}"

# Gemini API Key untuk AI Vision Multimodal Matching (Bisa diisi via environment variable atau diinput langsung di Web UI)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Font configuration (Windows default fallbacks)
SYSTEM_FONTS_DIR = Path("C:/Windows/Fonts")
FONT_BOLD_DEFAULT = str(SYSTEM_FONTS_DIR / "segoeuib.ttf") if (SYSTEM_FONTS_DIR / "segoeuib.ttf").exists() else str(SYSTEM_FONTS_DIR / "arialbd.ttf")
FONT_EXTRABOLD_DEFAULT = str(SYSTEM_FONTS_DIR / "segoeuiz.ttf") if (SYSTEM_FONTS_DIR / "segoeuiz.ttf").exists() else FONT_BOLD_DEFAULT
