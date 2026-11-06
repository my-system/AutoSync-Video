export interface VoiceoverTrack {
  id: string;
  project_id: string;
  filename: string;
  file_path: string;
  duration_seconds: number;
  sample_rate: number;
}

export interface Scene {
  id: string;
  project_id: string;
  scene_order: number;
  title?: string;
  raw_video_filename?: string;
  raw_video_path?: string;
  raw_video_duration: number;
  accent_color_hex: string;
  headline_text: string;
  script_text: string;
  start_time: number;
  end_time: number;
  target_duration: number;
  word_timestamps_json?: string;
  created_at: string;
}

export interface RenderJob {
  id: string;
  project_id: string;
  render_mode: string;
  status: 'QUEUED' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  progress_percent: number;
  current_step?: string;
  output_video_url?: string;
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface Project {
  id: string;
  title: string;
  aspect_ratio: string;
  output_fps: number;
  bgm_filename?: string;
  bgm_path?: string;
  bgm_volume?: number;
  overlay_y?: number;
  camera_motion?: string;
  transition_style?: string;
  created_at: string;
  updated_at: string;
  voiceover?: VoiceoverTrack;
  scenes: Scene[];
  render_jobs: RenderJob[];
}
