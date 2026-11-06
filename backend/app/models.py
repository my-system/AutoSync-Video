import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    aspect_ratio = Column(String(10), default="9:16")
    output_fps = Column(Integer, default=24)
    bgm_filename = Column(String(255), nullable=True)
    bgm_path = Column(Text, nullable=True)
    bgm_volume = Column(Float, default=0.15)
    overlay_y = Column(Integer, default=1380)
    camera_motion = Column(String(30), default="dynamic_zoom")
    transition_style = Column(String(30), default="clean_cut")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    voiceover = relationship("VoiceoverTrack", back_populates="project", uselist=False, cascade="all, delete-orphan")
    scenes = relationship("Scene", back_populates="project", order_by="Scene.scene_order", cascade="all, delete-orphan")
    render_jobs = relationship("RenderJob", back_populates="project", order_by="desc(RenderJob.created_at)", cascade="all, delete-orphan")

class VoiceoverTrack(Base):
    __tablename__ = "voiceover_tracks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    duration_seconds = Column(Float, default=0.0)
    sample_rate = Column(Integer, default=48000)

    project = relationship("Project", back_populates="voiceover")

class Scene(Base):
    __tablename__ = "scenes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    scene_order = Column(Integer, nullable=False)
    title = Column(String(150), nullable=True)
    raw_video_filename = Column(String(255), nullable=True)
    raw_video_path = Column(Text, nullable=True)
    raw_video_duration = Column(Float, default=0.0)
    
    accent_color_hex = Column(String(7), default="#38BDF8")
    headline_text = Column(String(255), nullable=True, default="")
    script_text = Column(Text, nullable=True, default="")
    
    start_time = Column(Float, default=0.0)
    end_time = Column(Float, default=0.0)
    target_duration = Column(Float, default=0.0)
    word_timestamps_json = Column(Text, nullable=True, default="[]")

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="scenes")

class RenderJob(Base):
    __tablename__ = "render_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    render_mode = Column(String(50), default="natural_text") # 'natural_text', 'compact_fixed', 'clean_no_text'
    status = Column(String(20), default="QUEUED") # QUEUED, PROCESSING, COMPLETED, FAILED
    progress_percent = Column(Integer, default=0)
    current_step = Column(String(255), default="Mengantre...")
    output_video_path = Column(Text, nullable=True)
    output_video_url = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    project = relationship("Project", back_populates="render_jobs")
