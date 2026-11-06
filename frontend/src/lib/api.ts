import { Project, Scene, RenderJob } from '../types';

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function fetchProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/api/v1/projects`);
  if (!res.ok) throw new Error('Gagal memuat daftar proyek');
  return res.json();
}

export async function fetchProject(id: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${id}`);
  if (!res.ok) throw new Error('Gagal memuat detail proyek');
  return res.json();
}

export async function createProject(title: string, aspect_ratio = '9:16', output_fps = 24): Promise<Project> {
  const res = await fetch(`${API_BASE}/api/v1/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, aspect_ratio, output_fps }),
  });
  if (!res.ok) throw new Error('Gagal membuat proyek baru');
  return res.json();
}

export async function deleteProject(id: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Gagal menghapus proyek');
  return res.json();
}

export async function generateStoryFromVideos(projectId: string, topic?: string, apiKey?: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/generate-story`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, api_key: apiKey }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Gagal membuat naskah otomatis dengan AI');
  }
  return res.json();
}

export async function uploadVoiceover(projectId: string, file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/api/v1/uploads/${projectId}/voiceover`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Gagal mengunggah voiceover');
  return res.json();
}

export async function uploadBgm(projectId: string, file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/api/v1/uploads/${projectId}/bgm`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Gagal mengunggah musik latar (BGM)');
  return res.json();
}

export async function deleteBgm(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/uploads/${projectId}/bgm`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Gagal menghapus musik latar (BGM)');
  return res.json();
}

export async function updateProject(projectId: string, data: Partial<Project>): Promise<Project> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Gagal memperbarui pengaturan proyek');
  return res.json();
}

export async function uploadScenes(projectId: string, files: File[]): Promise<any> {
  const formData = new FormData();
  for (const f of files) {
    formData.append('files', f);
  }
  const res = await fetch(`${API_BASE}/api/v1/uploads/${projectId}/videos`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Gagal mengunggah klip video');
  return res.json();
}

export async function uploadSceneSlotVideo(projectId: string, sceneId: string, file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/scenes/${sceneId}/upload-slot`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Gagal mengunggah klip ke slot adegan');
  return res.json();
}

export async function updateScene(projectId: string, sceneId: string, data: Partial<Scene>): Promise<Scene> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/scenes/${sceneId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    console.error('Update scene error details:', err);
    throw new Error(err.detail || 'Gagal memperbarui adegan');
  }
  return res.json();
}

export async function reorderScenes(projectId: string, sceneIds: string[]): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/scenes/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scene_ids: sceneIds }),
  });
  if (!res.ok) throw new Error('Gagal mengurutkan adegan');
  return res.json();
}

export async function deleteScene(projectId: string, sceneId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/scenes/${sceneId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Gagal menghapus adegan');
  return res.json();
}

export async function aiVisionMatch(projectId: string, apiKey?: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/ai-vision-match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Gagal menjalankan AI Vision Matcher');
  }
  return res.json();
}

export async function semanticMatch(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/semantic-match`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Gagal melakukan pencocokan semantik');
  }
  return res.json();
}

export async function loadTemplate(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/load-template`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Gagal memuat template');
  }
  return res.json();
}

export async function autoAlignScenes(projectId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/auto-align`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Gagal menjalankan auto-alignment');
  }
  return res.json();
}

export async function transcribeVoiceover(projectId: string, apiKey?: string, groqApiKey?: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/v1/projects/${projectId}/transcribe-voiceover`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey, groq_api_key: groqApiKey }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Gagal mentranskripsikan voiceover');
  }
  return res.json();
}

export async function triggerRender(
  projectId: string,
  render_mode: string,
  options?: {
    overlay_y?: number;
    camera_motion?: string;
    transition_style?: string;
    bgm_volume?: number;
  }
): Promise<RenderJob> {
  const res = await fetch(`${API_BASE}/api/v1/renders/${projectId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ render_mode, ...(options || {}) }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Gagal memulai render');
  }
  return res.json();
}

export async function getRenderStatus(jobId: string): Promise<RenderJob> {
  const res = await fetch(`${API_BASE}/api/v1/renders/${jobId}`);
  if (!res.ok) throw new Error('Gagal memuat status render');
  return res.json();
}
