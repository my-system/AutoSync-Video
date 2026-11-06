from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class SceneBase(BaseModel):
    scene_order: Optional[int] = 0
    title: Optional[str] = ""
    accent_color_hex: Optional[str] = "#38BDF8"
    headline_text: Optional[str] = ""
    script_text: Optional[str] = ""
    start_time: Optional[float] = 0.0
    end_time: Optional[float] = 0.0
    target_duration: Optional[float] = 0.0
    word_timestamps_json: Optional[str] = "[]"

class SceneUpdate(BaseModel):
    scene_order: Optional[int] = None
    title: Optional[str] = None
    accent_color_hex: Optional[str] = None
    headline_text: Optional[str] = None
    script_text: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    target_duration: Optional[float] = None
    word_timestamps_json: Optional[str] = None

class SceneResponse(SceneBase):
    id: str
    project_id: str
    raw_video_filename: Optional[str] = None
    raw_video_path: Optional[str] = None
    raw_video_duration: float = 0.0
    created_at: datetime

    class Config:
        from_attributes = True

class VoiceoverResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    file_path: str
    duration_seconds: float
    sample_rate: int

    class Config:
        from_attributes = True

class ProjectCreate(BaseModel):
    title: str = Field(..., example="Edukasi Jejak Digital")
    aspect_ratio: Optional[str] = "9:16"
    output_fps: Optional[int] = 24

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    aspect_ratio: Optional[str] = None
    output_fps: Optional[int] = None
    bgm_volume: Optional[float] = None
    overlay_y: Optional[int] = None
    camera_motion: Optional[str] = None
    transition_style: Optional[str] = None

class RenderJobResponse(BaseModel):
    id: str
    project_id: str
    render_mode: str
    status: str
    progress_percent: int
    current_step: Optional[str] = ""
    output_video_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ProjectDetailResponse(BaseModel):
    id: str
    title: str
    aspect_ratio: str
    output_fps: int
    bgm_filename: Optional[str] = None
    bgm_path: Optional[str] = None
    bgm_volume: Optional[float] = 0.15
    overlay_y: Optional[int] = 1380
    camera_motion: Optional[str] = "dynamic_zoom"
    transition_style: Optional[str] = "clean_cut"
    created_at: datetime
    updated_at: datetime
    voiceover: Optional[VoiceoverResponse] = None
    scenes: List[SceneResponse] = []
    render_jobs: List[RenderJobResponse] = []

    class Config:
        from_attributes = True

class RenderTriggerRequest(BaseModel):
    render_mode: Optional[str] = "natural_text" # natural_text, compact_fixed, clean_no_text
    overlay_y: Optional[int] = None
    camera_motion: Optional[str] = None
    transition_style: Optional[str] = None
    bgm_volume: Optional[float] = None
