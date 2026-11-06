import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text
from backend.app.database import Base, engine
from backend.app.config import STORAGE_DIR
from backend.app.api import projects, uploads, renders

# Buat tabel SQLite jika belum ada
Base.metadata.create_all(bind=engine)

# Auto-migrasi kolom baru pada SQLite tanpa menghapus data lama
def ensure_sqlite_columns():
    alter_statements = [
        "ALTER TABLE projects ADD COLUMN bgm_filename VARCHAR(255)",
        "ALTER TABLE projects ADD COLUMN bgm_path TEXT",
        "ALTER TABLE projects ADD COLUMN bgm_volume FLOAT DEFAULT 0.15",
        "ALTER TABLE projects ADD COLUMN overlay_y INTEGER DEFAULT 1380",
        "ALTER TABLE projects ADD COLUMN camera_motion VARCHAR(30) DEFAULT 'dynamic_zoom'",
        "ALTER TABLE projects ADD COLUMN transition_style VARCHAR(30) DEFAULT 'clean_cut'",
        "ALTER TABLE scenes ADD COLUMN word_timestamps_json TEXT DEFAULT '[]'",
    ]
    with engine.begin() as conn:
        for stmt in alter_statements:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass

ensure_sqlite_columns()

app = FastAPI(
    title="AutoSync Video Engine API",
    description="Automated Video & Voiceover Synchronization API (Local Desktop Edition)",
    version="1.0.0"
)

# Middleware CORS agar Next.js di frontend dapat mengakses API tanpa hambatan
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount folder storage lokal untuk preview berkas statis
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")

# Registrasi router API v1
app.include_router(projects.router, prefix="/api/v1")
app.include_router(uploads.router, prefix="/api/v1")
app.include_router(renders.router, prefix="/api/v1")

@app.get("/")
def root():
    return {
        "service": "AutoSync Video Engine",
        "status": "online",
        "docs_url": "/docs",
        "platform": "Local Edition"
    }

@app.get("/api/health")
def health():
    return {"status": "ok"}
