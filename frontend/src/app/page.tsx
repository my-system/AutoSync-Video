'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Video,
  Mic,
  Upload,
  Play,
  Download,
  RefreshCw,
  Plus,
  Trash2,
  Clock,
  Layers,
  Settings2,
  Sliders,
  FolderOpen,
  FileVideo,
  ArrowDownToLine,
  ArrowUp,
  ArrowDown,
  CheckCircle2,
  AlertCircle,
  FileText,
  Wand2,
  Brain,
  Key,
  Music,
  Eye,
  MoveVertical,
  Camera
} from 'lucide-react';
import { Project, Scene, RenderJob } from '../types';
import {
  fetchProjects,
  fetchProject,
  createProject,
  updateProject,
  uploadVoiceover,
  uploadBgm,
  deleteBgm,
  uploadScenes,
  uploadSceneSlotVideo,
  updateScene,
  reorderScenes,
  deleteScene,
  deleteProject,
  semanticMatch,
  aiVisionMatch,
  generateStoryFromVideos,
  loadTemplate,
  autoAlignScenes,
  transcribeVoiceover,
  triggerRender,
  getRenderStatus,
  API_BASE
} from '../lib/api';

const COLOR_PRESETS = [
  { name: 'Cyan Neon', hex: '#38BDF8' },
  { name: 'Yellow Gold', hex: '#FACC15' },
  { name: 'Emerald Green', hex: '#4ADE80' },
  { name: 'Purple Neon', hex: '#C084FC' },
  { name: 'Orange Flame', hex: '#FB923C' },
  { name: 'Rose Red', hex: '#F43F5E' },
];

export default function HomePage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);
  const [showApiModal, setShowApiModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [groqApiKey, setGroqApiKey] = useState('');

  // Muat API Key yang tersimpan di browser secara permanen
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const savedGemini = localStorage.getItem('autosync_gemini_api_key');
      if (savedGemini) setApiKey(savedGemini);
      const savedGroq = localStorage.getItem('autosync_groq_api_key');
      if (savedGroq) setGroqApiKey(savedGroq);
    }
  }, []);

  const handleSaveApiKeys = () => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('autosync_gemini_api_key', apiKey.trim());
      localStorage.setItem('autosync_groq_api_key', groqApiKey.trim());
    }
    setShowApiModal(false);
    setStatusMessage('API Key berhasil disimpan di peramban Anda!');
    setTimeout(() => setStatusMessage(''), 3500);
  };
  
  // Drag & Drop states for batch uploads
  const [isDraggingVo, setIsDraggingVo] = useState(false);
  const [isDraggingVid, setIsDraggingVid] = useState(false);
  const [isDraggingBgm, setIsDraggingBgm] = useState(false);

  // Drag states per scene slot
  const [dragSlotId, setDragSlotId] = useState<string | null>(null);

  // Render status & polling
  const [activeJob, setActiveJob] = useState<RenderJob | null>(null);
  const [renderMode, setRenderMode] = useState<string>('natural_text');
  const [overlayY, setOverlayY] = useState<number>(1380);
  const [cameraMotion, setCameraMotion] = useState<string>('dynamic_zoom');
  const [transitionStyle, setTransitionStyle] = useState<string>('clean_cut');
  const [bgmVolume, setBgmVolume] = useState<number>(0.15);
  const [previewTab, setPreviewTab] = useState<'live' | 'video'>('live');
  const [previewSceneIdx, setPreviewSceneIdx] = useState<number>(0);
  const [karaokeTick, setKaraokeTick] = useState<number>(0);
  const [isRendering, setIsRendering] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>('');

  const fileInputVoRef = useRef<HTMLInputElement>(null);
  const fileInputVidRef = useRef<HTMLInputElement>(null);
  const fileInputBgmRef = useRef<HTMLInputElement>(null);
  const slotInputRefs = useRef<{ [key: string]: HTMLInputElement | null }>({});

  // Animasi simulasi karaoke kata demi kata untuk Live Preview
  useEffect(() => {
    const timer = setInterval(() => {
      setKaraokeTick((prev) => prev + 1);
    }, 420);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    initProjects();
  }, []);

  async function initProjects() {
    try {
      setLoading(true);
      let list = await fetchProjects();
      if (list.length === 0) {
        const defaultProj = await createProject('Proyek Video 1');
        list = [defaultProj];
      }
      setProjects(list);
      if (list.length > 0) {
        selectProject(list[0].id);
      }
    } catch (err: any) {
      console.error('Error saat inisialisasi proyek:', err);
    } finally {
      setLoading(false);
    }
  }

  async function loadProjects() {
    try {
      const list = await fetchProjects();
      setProjects(list);
      return list;
    } catch (err: any) {
      console.error(err);
      return [];
    }
  }

  async function selectProject(id: string) {
    try {
      const proj = await fetchProject(id);
      setCurrentProject(proj);
      setOverlayY(proj.overlay_y ?? 1380);
      setCameraMotion(proj.camera_motion ?? 'dynamic_zoom');
      setTransitionStyle(proj.transition_style ?? 'clean_cut');
      setBgmVolume(proj.bgm_volume ?? 0.15);
      setPreviewSceneIdx(0);
      if (proj.render_jobs && proj.render_jobs.length > 0) {
        const latest = proj.render_jobs[0];
        setActiveJob(latest);
        if (latest.status === 'COMPLETED') {
          setPreviewTab('video');
        }
        if (latest.status === 'PROCESSING' || latest.status === 'QUEUED') {
          startPollingJob(latest.id);
        }
      } else {
        setActiveJob(null);
        setPreviewTab('live');
      }
    } catch (err: any) {
      alert('Gagal membuka proyek: ' + err.message);
    }
  }

  async function ensureActiveProject(): Promise<Project> {
    if (currentProject) return currentProject;
    const newProj = await createProject(`Proyek Video ${projects.length + 1}`);
    await loadProjects();
    setCurrentProject(newProj);
    return newProj;
  }

  async function handleCreateProject() {
    if (!newTitle.trim()) return;
    try {
      setLoading(true);
      const created = await createProject(newTitle.trim());
      setShowNewModal(false);
      setNewTitle('');
      await loadProjects();
      selectProject(created.id);
    } catch (err: any) {
      alert('Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  // Hapus proyek aktif beserta seluruh datanya
  async function handleDeleteCurrentProject() {
    if (!currentProject) return;
    const confirmed = confirm(`Apakah Anda yakin ingin menghapus proyek "${currentProject.title}" beserta seluruh klip adegannya?`);
    if (!confirmed) return;

    try {
      setLoading(true);
      setStatusMessage('Menghapus proyek...');
      await deleteProject(currentProject.id);
      const remaining = await loadProjects();
      if (remaining.length > 0) {
        await selectProject(remaining[0].id);
      } else {
        const fresh = await createProject('Proyek Video 1');
        await loadProjects();
        await selectProject(fresh.id);
      }
      setStatusMessage('Proyek berhasil dihapus!');
      setTimeout(() => setStatusMessage(''), 3000);
    } catch (err: any) {
      alert('Gagal menghapus proyek: ' + err.message);
      setStatusMessage('');
    } finally {
      setLoading(false);
    }
  }

  async function processVoiceoverFile(file: File) {
    try {
      setStatusMessage('Mengunggah dan menganalisis audio voiceover...');
      const proj = await ensureActiveProject();
      await uploadVoiceover(proj.id, file);
      await selectProject(proj.id);
      setStatusMessage('Voiceover berhasil diunggah!');
      setTimeout(() => setStatusMessage(''), 3500);
    } catch (err: any) {
      alert('Gagal unggah voiceover: ' + err.message);
      setStatusMessage('');
    }
  }

  function handleFileInputVoChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.[0]) {
      processVoiceoverFile(e.target.files[0]);
    }
    e.target.value = '';
  }

  function handleDropVoiceover(e: React.DragEvent) {
    e.preventDefault();
    setIsDraggingVo(false);
    const files = Array.from(e.dataTransfer.files);
    const audioFile = files.find((f) => f.type.startsWith('audio/') || /\.(mp3|wav|m4a|aac|ogg)$/i.test(f.name));
    if (audioFile) {
      processVoiceoverFile(audioFile);
    } else if (files.length > 0) {
      alert('Silakan tarik berkas audio (.mp3 atau .wav)');
    }
  }

  async function processVideoFiles(files: File[]) {
    try {
      const sorted = Array.from(files).sort((a, b) =>
        a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' })
      );
      setStatusMessage(`Mengunggah ${sorted.length} klip video...`);
      const proj = await ensureActiveProject();
      await uploadScenes(proj.id, sorted);
      await selectProject(proj.id);
      setStatusMessage('Video adegan berhasil diunggah!');
      setTimeout(() => setStatusMessage(''), 3500);
    } catch (err: any) {
      alert('Gagal unggah video: ' + err.message);
      setStatusMessage('');
    }
  }

  function handleFileInputVidChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files.length > 0) {
      processVideoFiles(Array.from(e.target.files));
    }
    e.target.value = '';
  }

  function handleDropVideos(e: React.DragEvent) {
    e.preventDefault();
    setIsDraggingVid(false);
    const files = Array.from(e.dataTransfer.files);
    const videoFiles = files.filter((f) => f.type.startsWith('video/') || /\.(mp4|mov|webm|mkv|avi)$/i.test(f.name));
    if (videoFiles.length > 0) {
      processVideoFiles(videoFiles);
    } else if (files.length > 0) {
      alert('Silakan tarik berkas video (.mp4 atau .mov)');
    }
  }

  // Upload langsung ke slot spesifik per adegan
  async function handleSlotUpload(sceneId: string, file: File) {
    if (!currentProject) return;
    try {
      setStatusMessage('Memasang klip video ke slot adegan...');
      await uploadSceneSlotVideo(currentProject.id, sceneId, file);
      await selectProject(currentProject.id);
      setStatusMessage('Klip berhasil dipasang!');
      setTimeout(() => setStatusMessage(''), 3000);
    } catch (err: any) {
      alert('Gagal pasang klip: ' + err.message);
      setStatusMessage('');
    }
  }

  async function handleSceneChange(sceneId: string, updates: Partial<Scene>) {
    if (!currentProject) return;
    setCurrentProject({
      ...currentProject,
      scenes: currentProject.scenes.map((s) => (s.id === sceneId ? { ...s, ...updates } : s)),
    });
    try {
      await updateScene(currentProject.id, sceneId, updates);
    } catch (err: any) {
      console.error('Gagal update adegan:', err);
    }
  }

  async function handleMoveSceneUp(idx: number) {
    if (!currentProject || idx <= 0) return;
    const newScenes = [...currentProject.scenes];
    const temp = newScenes[idx];
    newScenes[idx] = newScenes[idx - 1];
    newScenes[idx - 1] = temp;

    setCurrentProject({ ...currentProject, scenes: newScenes });
    const newIds = newScenes.map((s) => s.id);
    await reorderScenes(currentProject.id, newIds);
    await selectProject(currentProject.id);
  }

  async function handleMoveSceneDown(idx: number) {
    if (!currentProject || idx >= currentProject.scenes.length - 1) return;
    const newScenes = [...currentProject.scenes];
    const temp = newScenes[idx];
    newScenes[idx] = newScenes[idx + 1];
    newScenes[idx + 1] = temp;

    setCurrentProject({ ...currentProject, scenes: newScenes });
    const newIds = newScenes.map((s) => s.id);
    await reorderScenes(currentProject.id, newIds);
    await selectProject(currentProject.id);
  }

  async function handleDeleteScene(sceneId: string) {
    if (!currentProject) return;
    if (!confirm('Yakin ingin menghapus adegan ini?')) return;
    try {
      await deleteScene(currentProject.id, sceneId);
      await selectProject(currentProject.id);
    } catch (err: any) {
      alert('Gagal menghapus adegan: ' + err.message);
    }
  }

  // Muat template data naskah 7 adegan (Jejak Digital)
  async function handleLoadTemplate() {
    if (!currentProject) return;
    try {
      setStatusMessage('Memuat template 7 adegan Jejak Digital...');
      await loadTemplate(currentProject.id);
      await selectProject(currentProject.id);
      setStatusMessage('Template 7 adegan berhasil dimuat!');
      setTimeout(() => setStatusMessage(''), 3000);
    } catch (err: any) {
      alert('Gagal memuat template: ' + err.message);
      setStatusMessage('');
    }
  }

  // Pencocokan semantik otomatis (Visual-to-Script Keyword Matcher)
  async function handleSemanticMatch() {
    if (!currentProject) return;
    try {
      setStatusMessage('Mencocokkan klip video dengan naskah adegan secara semantik...');
      const res = await semanticMatch(currentProject.id);
      await selectProject(currentProject.id);
      setStatusMessage(res.message || 'Pencocokan semantik selesai!');
      setTimeout(() => setStatusMessage(''), 4000);
    } catch (err: any) {
      alert('Pencocokan semantik gagal: ' + err.message);
      setStatusMessage('');
    }
  }

  // Pencocokan otomatis menggunakan Gemini 3.5 Flash Vision Multimodal
  async function handleVisionMatch() {
    if (!currentProject) return;
    try {
      setStatusMessage('Mengekstrak frame video & menganalisis konten visual dengan Gemini 3.5 Flash...');
      const res = await aiVisionMatch(currentProject.id, apiKey);
      await selectProject(currentProject.id);
      setStatusMessage(res.message || 'Pencocokan visual AI Vision selesai!');
      setTimeout(() => setStatusMessage(''), 4500);
    } catch (err: any) {
      alert('AI Vision Matcher gagal: ' + err.message);
      setStatusMessage('');
    }
  }

  // AI Storyteller: Menganalisis visual video & otomatis mengisi lencana judul, naskah narasi, dan warna aksen
  async function handleGenerateStory() {
    if (!currentProject) return;
    const topic = prompt('Masukkan tema/topik video Anda (opsional, contoh: "Edukasi Jejak Digital"):', currentProject.title || '');
    if (topic === null) return;

    try {
      setStatusMessage('AI Storyteller sedang membaca frame video & menyusun naskah serta lencana judul...');
      const res = await generateStoryFromVideos(currentProject.id, topic, apiKey);
      await selectProject(currentProject.id);
      setStatusMessage(res.message || 'Naskah dan lencana berhasil dibuat secara otomatis!');
      setTimeout(() => setStatusMessage(''), 4500);
    } catch (err: any) {
      alert('AI Storyteller gagal: ' + err.message);
      setStatusMessage('');
    }
  }

  async function handleAutoAlign() {
    if (!currentProject) return;
    try {
      setStatusMessage('Menyelaraskan jeda narasi audio...');
      await autoAlignScenes(currentProject.id);
      await selectProject(currentProject.id);
      setStatusMessage('Penyelarasan jeda hening selesai!');
      setTimeout(() => setStatusMessage(''), 3500);
    } catch (err: any) {
      alert('Auto-align gagal: ' + err.message);
      setStatusMessage('');
    }
  }

  // Transkripsi Voiceover: Mendengarkan audio asli narator dan otomatis mengisi naskah narasi & lencana judul
  async function handleTranscribeVoiceover() {
    if (!currentProject) return;
    if (!currentProject.voiceover) {
      alert('Silakan unggah berkas audio Voiceover terlebih dahulu!');
      return;
    }

    try {
      setStatusMessage('Sistem sedang mendengarkan rekaman suara & mentranskripsikan seluruh adegan sekaligus...');
      const res = await transcribeVoiceover(currentProject.id, apiKey, groqApiKey);
      await selectProject(currentProject.id);
      setStatusMessage(res.message || 'Naskah berhasil ditranskripsikan langsung dari rekaman suara narator!');
      setTimeout(() => setStatusMessage(''), 4500);
    } catch (err: any) {
      alert('Transkripsi suara gagal: ' + err.message);
      setStatusMessage('');
    }
  }

  async function handleStartRender() {
    if (!currentProject) return;
    try {
      setIsRendering(true);
      const job = await triggerRender(currentProject.id, renderMode, {
        overlay_y: overlayY,
        camera_motion: cameraMotion,
        transition_style: transitionStyle,
        bgm_volume: bgmVolume,
      });
      setActiveJob(job);
      setPreviewTab('video');
      startPollingJob(job.id);
    } catch (err: any) {
      alert('Gagal memulai render: ' + err.message);
      setIsRendering(false);
    }
  }

  async function processBgmFile(file: File) {
    try {
      setStatusMessage('Mengunggah Musik Latar (BGM) & menyiapkan Auto-Ducking...');
      const proj = await ensureActiveProject();
      await uploadBgm(proj.id, file);
      await selectProject(proj.id);
      setStatusMessage('Musik Latar (BGM) berhasil dipasang!');
      setTimeout(() => setStatusMessage(''), 3500);
    } catch (err: any) {
      alert('Gagal unggah BGM: ' + err.message);
      setStatusMessage('');
    }
  }

  async function handleDeleteBgm(e: React.MouseEvent) {
    e.stopPropagation();
    if (!currentProject) return;
    try {
      await deleteBgm(currentProject.id);
      await selectProject(currentProject.id);
      setStatusMessage('Musik Latar (BGM) dihapus.');
      setTimeout(() => setStatusMessage(''), 2500);
    } catch (err: any) {
      alert('Gagal hapus BGM: ' + err.message);
    }
  }

  async function handleProjectSettingChange(updates: Partial<Project>) {
    if (!currentProject) return;
    if (updates.overlay_y !== undefined) setOverlayY(updates.overlay_y);
    if (updates.camera_motion !== undefined) setCameraMotion(updates.camera_motion);
    if (updates.transition_style !== undefined) setTransitionStyle(updates.transition_style);
    if (updates.bgm_volume !== undefined) setBgmVolume(updates.bgm_volume);
    try {
      await updateProject(currentProject.id, updates);
    } catch (e) {
      console.error(e);
    }
  }

  function startPollingJob(jobId: string) {
    setIsRendering(true);
    const interval = setInterval(async () => {
      try {
        const status = await getRenderStatus(jobId);
        setActiveJob(status);
        if (status.status === 'COMPLETED' || status.status === 'FAILED') {
          clearInterval(interval);
          setIsRendering(false);
          if (currentProject) {
            const p = await fetchProject(currentProject.id);
            setCurrentProject(p);
          }
        }
      } catch (e) {
        clearInterval(interval);
        setIsRendering(false);
      }
    }, 1000);
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur px-6 py-3.5 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/25">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-bold text-base tracking-tight text-white">AutoSync Video</h1>
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800/80">
                Desktop Local Edition
              </span>
            </div>
            <p className="text-xs text-slate-400">Automated Video & Voiceover Synchronization Engine</p>
          </div>
        </div>

        {/* Project Switcher & New Button */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs">
            <FolderOpen className="w-3.5 h-3.5 text-cyan-400" />
            <select
              value={currentProject?.id || ''}
              onChange={(e) => selectProject(e.target.value)}
              className="bg-transparent text-slate-200 focus:outline-none cursor-pointer"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id} className="bg-slate-900 text-white">
                  {p.title}
                </option>
              ))}
            </select>

            {currentProject && (
              <button
                type="button"
                onClick={handleDeleteCurrentProject}
                title={`Hapus proyek "${currentProject.title}"`}
                className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 rounded transition cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <button
            onClick={() => setShowApiModal(true)}
            title="Pengaturan Gemini API Key"
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-xs rounded-lg transition cursor-pointer"
          >
            <Key className="w-3.5 h-3.5 text-amber-400" />
            <span className="hidden sm:inline">Gemini API</span>
            {apiKey ? (
              <span className="w-2 h-2 rounded-full bg-emerald-400 ring-2 ring-emerald-400/20" title="API Key Aktif" />
            ) : (
              <span className="w-2 h-2 rounded-full bg-amber-400 ring-2 ring-amber-400/20 animate-pulse" title="Belum Diisi" />
            )}
          </button>

          <button
            onClick={() => setShowNewModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-xs rounded-lg transition shadow-md shadow-cyan-500/20 cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            Proyek Baru
          </button>
        </div>
      </header>

      {/* Main Content Workspace */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Media Uploader & Scene Timeline Editor (Col 7/12) */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          {/* Status Alert Banner */}
          {statusMessage && (
            <div className="bg-cyan-950/80 border border-cyan-700 rounded-xl px-4 py-2.5 flex items-center gap-2 text-xs text-cyan-300 shadow-md">
              <RefreshCw className="w-4 h-4 animate-spin text-cyan-400" />
              <span>{statusMessage}</span>
            </div>
          )}

          {/* Section 1: Upload Assets (Voiceover & Raw Clips with Drag and Drop) */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-semibold tracking-wide text-white">Aset Media Masukan</h2>
              </div>
              <span className="text-xs text-slate-400">Rasio 9:16 Vertikal (1080x1920)</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Voiceover Upload / Drop Card */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDraggingVo(true);
                }}
                onDragLeave={() => setIsDraggingVo(false)}
                onDrop={handleDropVoiceover}
                onClick={() => fileInputVoRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-5 cursor-pointer transition flex flex-col items-center justify-center text-center gap-2.5 relative group ${
                  isDraggingVo
                    ? 'border-cyan-400 bg-cyan-950/40 scale-[1.02] shadow-lg shadow-cyan-500/20'
                    : currentProject?.voiceover
                    ? 'border-emerald-500/60 bg-emerald-950/20 hover:bg-emerald-950/30'
                    : 'border-slate-700 bg-slate-950/50 hover:border-cyan-500/70 hover:bg-slate-900/60'
                }`}
              >
                <input
                  type="file"
                  ref={fileInputVoRef}
                  onChange={handleFileInputVoChange}
                  accept=".mp3,.wav,.m4a,.aac,.ogg,audio/*"
                  className="hidden"
                />

                <div
                  className={`w-11 h-11 rounded-full flex items-center justify-center transition ${
                    isDraggingVo
                      ? 'bg-cyan-500 text-slate-950 scale-110'
                      : currentProject?.voiceover
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-slate-800 text-slate-300 group-hover:bg-cyan-500/20 group-hover:text-cyan-300'
                  }`}
                >
                  {isDraggingVo ? <ArrowDownToLine className="w-5 h-5 animate-bounce" /> : <Mic className="w-5 h-5" />}
                </div>

                <div>
                  <p className="text-xs font-semibold text-slate-200">
                    {isDraggingVo
                      ? 'Lepaskan File Voiceover di Sini!'
                      : currentProject?.voiceover
                      ? currentProject.voiceover.filename
                      : 'Unggah / Tarik File Voiceover'}
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    {currentProject?.voiceover
                      ? `Durasi: ${currentProject.voiceover.duration_seconds.toFixed(2)}s (Klik/tarik untuk ganti)`
                      : 'Klik pilih atau Drag & Drop berkas audio (.mp3 / .wav)'}
                  </p>
                </div>
              </div>

              {/* Video Clips Upload / Drop Card */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDraggingVid(true);
                }}
                onDragLeave={() => setIsDraggingVid(false)}
                onDrop={handleDropVideos}
                onClick={() => fileInputVidRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-5 cursor-pointer transition flex flex-col items-center justify-center text-center gap-2.5 relative group ${
                  isDraggingVid
                    ? 'border-cyan-400 bg-cyan-950/40 scale-[1.02] shadow-lg shadow-cyan-500/20'
                    : currentProject?.scenes && currentProject.scenes.length > 0
                    ? 'border-cyan-500/60 bg-cyan-950/20 hover:bg-cyan-950/30'
                    : 'border-slate-700 bg-slate-950/50 hover:border-cyan-500/70 hover:bg-slate-900/60'
                }`}
              >
                <input
                  type="file"
                  ref={fileInputVidRef}
                  onChange={handleFileInputVidChange}
                  multiple
                  accept=".mp4,.mov,.webm,.mkv,.avi,video/*"
                  className="hidden"
                />

                <div
                  className={`w-11 h-11 rounded-full flex items-center justify-center transition ${
                    isDraggingVid
                      ? 'bg-cyan-500 text-slate-950 scale-110'
                      : currentProject?.scenes && currentProject.scenes.length > 0
                      ? 'bg-cyan-500/20 text-cyan-400'
                      : 'bg-slate-800 text-slate-300 group-hover:bg-cyan-500/20 group-hover:text-cyan-300'
                  }`}
                >
                  {isDraggingVid ? <ArrowDownToLine className="w-5 h-5 animate-bounce" /> : <Video className="w-5 h-5" />}
                </div>

                <div>
                  <p className="text-xs font-semibold text-slate-200">
                    {isDraggingVid
                      ? 'Lepaskan Klip Video di Sini!'
                      : currentProject?.scenes && currentProject.scenes.length > 0
                      ? `${currentProject.scenes.length} Klip Video Terunggah`
                      : 'Unggah / Tarik Kumpulan Video'}
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    {currentProject?.scenes && currentProject.scenes.length > 0
                      ? 'Klik / Tarik untuk menambah klip video lagi'
                      : 'Pilih sekaligus beberapa klip video mentah (.mp4)'}
                  </p>
                </div>
              </div>
            </div>

            {/* Background Music (BGM) Upload + Smart Auto-Ducking Card */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDraggingBgm(true);
              }}
              onDragLeave={() => setIsDraggingBgm(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDraggingBgm(false);
                const files = Array.from(e.dataTransfer.files);
                const audioFile = files.find((f) => f.type.startsWith('audio/') || /\.(mp3|wav|m4a|aac|ogg)$/i.test(f.name));
                if (audioFile) processBgmFile(audioFile);
              }}
              onClick={() => fileInputBgmRef.current?.click()}
              className={`mt-3.5 border border-dashed rounded-xl p-3.5 cursor-pointer transition flex flex-wrap items-center justify-between gap-3 ${
                isDraggingBgm
                  ? 'border-purple-400 bg-purple-950/40'
                  : currentProject?.bgm_filename
                  ? 'border-purple-500/50 bg-purple-950/15 hover:bg-purple-950/25'
                  : 'border-slate-800 bg-slate-950/40 hover:border-purple-500/50'
              }`}
            >
              <input
                type="file"
                ref={fileInputBgmRef}
                onChange={(e) => {
                  if (e.target.files?.[0]) processBgmFile(e.target.files[0]);
                  e.target.value = '';
                }}
                accept=".mp3,.wav,.m4a,.aac,.ogg,audio/*"
                className="hidden"
              />
              <div className="flex items-center gap-3">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center ${
                  currentProject?.bgm_filename ? 'bg-purple-500/20 text-purple-300' : 'bg-slate-800 text-slate-400'
                }`}>
                  <Music className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                    <span>
                      {currentProject?.bgm_filename
                        ? `BGM: ${currentProject.bgm_filename}`
                        : 'Musik Latar / BGM (Opsional • Smart Auto-Ducking)'}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800/70">
                      Sidechain Ducking
                    </span>
                  </p>
                  <p className="text-[11px] text-slate-400">
                    {currentProject?.bgm_filename
                      ? 'Musik otomatis mengecil saat narator bicara & mengalir nyambung antar adegan'
                      : 'Klik atau tarik file musik (.mp3/.wav) untuk latar belakang video'}
                  </p>
                </div>
              </div>

              {currentProject?.bgm_filename && (
                <div className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center gap-2 text-[11px] text-slate-300">
                    <span>Vol: {Math.round(bgmVolume * 100)}%</span>
                    <input
                      type="range"
                      min="0.05"
                      max="0.45"
                      step="0.01"
                      value={bgmVolume}
                      onChange={(e) => handleProjectSettingChange({ bgm_volume: parseFloat(e.target.value) })}
                      className="w-20 accent-purple-400 cursor-pointer"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleDeleteBgm}
                    title="Hapus BGM"
                    className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-rose-400 hover:bg-rose-950/50 transition cursor-pointer"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>

            {/* Auto-Align Button */}
            {currentProject?.voiceover && currentProject.scenes.length > 0 && (
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                <span className="text-xs text-slate-400">Penyelarasan napas FFmpeg</span>
                <button
                  onClick={handleAutoAlign}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-medium rounded-lg transition border border-slate-700 cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
                  Auto-Align Jeda Napas (Silence Detect)
                </button>
              </div>
            )}
          </div>

          {/* Section 2: Scene Timeline & Editor with Semantic Matcher */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-semibold tracking-wide text-white">
                  Penyusunan Adegan & Pencocokan Naskah
                </h2>
              </div>

              {/* Action Buttons: Template & Semantic Match */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleLoadTemplate}
                  title="Muat alur naskah data (Kantor, Kota, Supermarket, dll.)"
                  className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-medium transition cursor-pointer"
                >
                  <FileText className="w-3.5 h-3.5 text-amber-400" />
                  Muat Template 7 Adegan
                </button>

                <button
                  type="button"
                  onClick={handleSemanticMatch}
                  title="Cocokkan video ke adegan berdasarkan kata kunci nama berkas"
                  className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-xs font-medium transition cursor-pointer"
                >
                  <Wand2 className="w-3.5 h-3.5 text-cyan-400" />
                  Semantik Nama
                </button>

                <button
                  type="button"
                  onClick={handleTranscribeVoiceover}
                  title="Dengarkan rekaman voiceover dan otomatis isi naskah & judul adegan sesuai kata-kata asli yang diucapkan narator!"
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-600 hover:opacity-90 text-white rounded-lg text-xs font-bold shadow-md shadow-blue-500/20 transition cursor-pointer"
                >
                  <Mic className="w-3.5 h-3.5 text-cyan-200 animate-pulse" />
                  Transkripsi Suara (Gemini)
                </button>

                <button
                  type="button"
                  onClick={handleVisionMatch}
                  title="Ekstrak frame video & gunakan Gemini 3.5 Flash Vision untuk mencocokkan adegan secara visual"
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-amber-500 via-purple-600 to-cyan-500 hover:opacity-90 text-white rounded-lg text-xs font-bold shadow-md shadow-purple-500/20 transition cursor-pointer"
                >
                  <Brain className="w-3.5 h-3.5 text-amber-200" />
                  AI Vision Match
                </button>

                <button
                  type="button"
                  onClick={handleGenerateStory}
                  title="AI Storyteller: Menganalisis frame klip video dan otomatis membuatkan lencana judul & naskah narasi!"
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-emerald-500 via-teal-600 to-cyan-600 hover:opacity-90 text-white rounded-lg text-xs font-bold shadow-md shadow-emerald-500/20 transition cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-300 animate-pulse" />
                  AI Storyteller (Isi Naskah)
                </button>
              </div>
            </div>

            {(!currentProject?.scenes || currentProject.scenes.length === 0) ? (
              <div className="text-center py-12 border border-dashed border-slate-800 rounded-xl text-slate-500 text-xs flex flex-col items-center gap-2">
                <FileVideo className="w-8 h-8 text-slate-600" />
                <p>Belum ada daftar adegan.</p>
                <div className="flex items-center gap-2 mt-2">
                  <button
                    onClick={handleLoadTemplate}
                    className="px-3 py-1.5 bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 rounded-lg text-xs font-medium transition cursor-pointer"
                  >
                    Klik untuk Memuat Template 7 Adegan
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {currentProject.scenes.map((scene, idx) => {
                  const ptsFactor =
                    scene.raw_video_duration > 0
                      ? scene.target_duration / scene.raw_video_duration
                      : 1.0;

                  const isSlotDragging = dragSlotId === scene.id;

                  return (
                    <div
                      key={scene.id}
                      className="bg-slate-950/70 border border-slate-800/90 hover:border-slate-700 rounded-xl p-4.5 transition flex flex-col gap-3.5"
                    >
                      {/* Scene Header with Move Up/Down & Delete buttons */}
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="w-5 h-5 rounded-md bg-cyan-950 text-cyan-400 border border-cyan-800 flex items-center justify-center font-bold text-[10px]">
                            {idx + 1}
                          </span>
                          <span className="font-semibold text-slate-200">
                            {scene.title || `Adegan ${idx + 1}`}
                          </span>
                        </div>

                        {/* Action buttons: Move Up, Move Down, Delete, and PTS indicator */}
                        <div className="flex items-center gap-2">
                          {/* Reorder Buttons */}
                          <div className="flex items-center bg-slate-900 rounded border border-slate-800 overflow-hidden">
                            <button
                              type="button"
                              disabled={idx === 0}
                              onClick={() => handleMoveSceneUp(idx)}
                              title="Pindahkan ke atas"
                              className="px-1.5 py-1 text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer"
                            >
                              <ArrowUp className="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              disabled={idx === currentProject.scenes.length - 1}
                              onClick={() => handleMoveSceneDown(idx)}
                              title="Pindahkan ke bawah"
                              className="px-1.5 py-1 text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-30 disabled:hover:bg-transparent border-l border-slate-800 cursor-pointer"
                            >
                              <ArrowDown className="w-3 h-3" />
                            </button>
                          </div>

                          {/* Delete Scene Button */}
                          <button
                            type="button"
                            onClick={() => handleDeleteScene(scene.id)}
                            title="Hapus adegan ini"
                            className="p-1 rounded bg-slate-900 border border-slate-800 text-rose-400 hover:bg-rose-950/40 hover:border-rose-800 transition cursor-pointer"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>

                          {/* PTS Speed Scaling Indicator */}
                          <div className="flex items-center gap-1.5 bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-[11px]">
                            <Clock className="w-3 h-3 text-slate-400" />
                            <span className="text-slate-300 font-mono">
                              {scene.target_duration.toFixed(2)}s
                            </span>
                            <span className="text-slate-500">|</span>
                            <span
                              className={`font-mono ${
                                ptsFactor > 1.05 ? 'text-amber-400' : 'text-cyan-400'
                              }`}
                            >
                              PTS {ptsFactor.toFixed(2)}x
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* DEDICATED VIDEO SLOT PER SCENE CARD (Slot Dropzone) */}
                      <div
                        onDragOver={(e) => {
                          e.preventDefault();
                          setDragSlotId(scene.id);
                        }}
                        onDragLeave={() => setDragSlotId(null)}
                        onDrop={(e) => {
                          e.preventDefault();
                          setDragSlotId(null);
                          const files = Array.from(e.dataTransfer.files);
                          const vid = files.find((f) => f.type.startsWith('video/') || /\.(mp4|mov|webm)$/i.test(f.name));
                          if (vid) {
                            handleSlotUpload(scene.id, vid);
                          }
                        }}
                        onClick={() => slotInputRefs.current[scene.id]?.click()}
                        className={`rounded-lg p-2.5 border transition flex items-center justify-between cursor-pointer ${
                          isSlotDragging
                            ? 'border-cyan-400 bg-cyan-950/40 scale-[1.01]'
                            : scene.raw_video_filename
                            ? 'border-slate-800 bg-slate-900/60 hover:border-cyan-500/50'
                            : 'border-dashed border-amber-500/40 bg-amber-950/10 hover:border-amber-400'
                        }`}
                      >
                        <input
                          type="file"
                          ref={(el) => {
                            slotInputRefs.current[scene.id] = el;
                          }}
                          onChange={(e) => {
                            if (e.target.files?.[0]) {
                              handleSlotUpload(scene.id, e.target.files[0]);
                            }
                            e.target.value = '';
                          }}
                          accept=".mp4,.mov,.webm,.mkv,video/*"
                          className="hidden"
                        />

                        <div className="flex items-center gap-2.5 overflow-hidden">
                          <div
                            className={`w-7 h-7 rounded flex items-center justify-center shrink-0 ${
                              scene.raw_video_filename
                                ? 'bg-cyan-500/20 text-cyan-400'
                                : 'bg-amber-500/20 text-amber-400'
                            }`}
                          >
                            <Video className="w-3.5 h-3.5" />
                          </div>
                          <div className="truncate">
                            <p className="text-xs font-medium text-slate-200 truncate">
                              {scene.raw_video_filename ? (
                                <span className="font-mono text-cyan-300">{scene.raw_video_filename}</span>
                              ) : (
                                <span className="text-amber-400">Belum ada video di slot ini (Tarik video ke sini)</span>
                              )}
                            </p>
                            <p className="text-[10px] text-slate-500">
                              {scene.raw_video_filename
                                ? `Durasi klip: ${scene.raw_video_duration.toFixed(2)}s • Klik / tarik untuk menukar`
                                : 'Klik atau Drag & Drop berkas video khusus untuk adegan ini'}
                            </p>
                          </div>
                        </div>

                        <span className="text-[10px] font-semibold text-slate-400 px-2 py-0.5 rounded bg-slate-800 shrink-0">
                          Slot #{idx + 1}
                        </span>
                      </div>

                      {/* Headline Pill Badge Input & Color Picker */}
                      <div className="flex flex-col gap-1.5">
                        <div className="flex items-center justify-between text-[11px] text-slate-400">
                          <label className="font-medium">Lencana Judul (CapCut Pill Badge)</label>
                          {/* Accent Color Chooser */}
                          <div className="flex items-center gap-1">
                            {COLOR_PRESETS.map((c) => (
                              <button
                                key={c.hex}
                                type="button"
                                title={c.name}
                                onClick={() => handleSceneChange(scene.id, { accent_color_hex: c.hex })}
                                className={`w-3.5 h-3.5 rounded-full border transition cursor-pointer ${
                                  scene.accent_color_hex === c.hex
                                    ? 'border-white scale-110 shadow-sm'
                                    : 'border-transparent opacity-60 hover:opacity-100'
                                }`}
                                style={{ backgroundColor: c.hex }}
                              />
                            ))}
                          </div>
                        </div>

                        <input
                          type="text"
                          value={scene.headline_text || ''}
                          onChange={(e) => handleSceneChange(scene.id, { headline_text: e.target.value })}
                          placeholder="Contoh: Kamu meninggalkan jejak"
                          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition"
                        />
                      </div>

                      {/* Script Narrative Text Input */}
                      <div className="flex flex-col gap-1.5">
                        <div className="flex items-center justify-between text-[11px] text-slate-400">
                          <label className="font-medium">Naskah Suara / Takarir Dinamis</label>
                          <span className="text-[10px] text-slate-500">
                            Gunakan [kata] untuk highlight neon
                          </span>
                        </div>
                        <textarea
                          rows={2}
                          value={scene.script_text || ''}
                          onChange={(e) => handleSceneChange(scene.id, { script_text: e.target.value })}
                          placeholder="Tulis naskah narasi di sini. Pisahkan dengan tanda / untuk pergantian frasa bertahap..."
                          className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition leading-relaxed resize-none"
                        />
                      </div>

                      {/* Timing Sync Inputs */}
                      <div className="grid grid-cols-3 gap-2.5 pt-1 text-[11px]">
                        <div>
                          <span className="text-slate-400">Mulai VO (s)</span>
                          <input
                            type="number"
                            step="0.05"
                            value={scene.start_time}
                            onChange={(e) => {
                              const val = parseFloat(e.target.value) || 0;
                              handleSceneChange(scene.id, {
                                start_time: val,
                                target_duration: Math.max(0.5, scene.end_time - val),
                              });
                            }}
                            className="w-full mt-1 bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                          />
                        </div>

                        <div>
                          <span className="text-slate-400">Selesai VO (s)</span>
                          <input
                            type="number"
                            step="0.05"
                            value={scene.end_time}
                            onChange={(e) => {
                              const val = parseFloat(e.target.value) || 0;
                              handleSceneChange(scene.id, {
                                end_time: val,
                                target_duration: Math.max(0.5, val - scene.start_time),
                              });
                            }}
                            className="w-full mt-1 bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                          />
                        </div>

                        <div>
                          <span className="text-slate-400">Durasi Target (s)</span>
                          <input
                            type="number"
                            step="0.05"
                            value={scene.target_duration}
                            onChange={(e) => {
                              const val = parseFloat(e.target.value) || 0.5;
                              handleSceneChange(scene.id, {
                                target_duration: val,
                                end_time: scene.start_time + val,
                              });
                            }}
                            className="w-full mt-1 bg-slate-900 border border-slate-800 rounded px-2 py-1 text-cyan-300 font-mono font-semibold focus:outline-none focus:border-cyan-500"
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Mode Selector, Trigger & Video Preview Player (Col 5/12) */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          {/* Render Mode & Trigger Card */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <Settings2 className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold tracking-wide text-white">Mode Rendering</h2>
            </div>

            <div className="flex flex-col gap-2.5">
              {/* Mode A */}
              <label
                onClick={() => setRenderMode('natural_text')}
                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition ${
                  renderMode === 'natural_text'
                    ? 'border-cyan-500 bg-cyan-950/20'
                    : 'border-slate-800 bg-slate-950/40 hover:border-slate-700'
                }`}
              >
                <input
                  type="radio"
                  name="render_mode"
                  checked={renderMode === 'natural_text'}
                  onChange={() => setRenderMode('natural_text')}
                  className="mt-0.5 text-cyan-500 focus:ring-0 cursor-pointer"
                />
                <div>
                  <p className="text-xs font-semibold text-white flex items-center gap-1.5">
                    <span>Mode A: Takarir Nyala Per Kata (Karaoke)</span>
                    <span className="px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 text-[10px] font-bold">Populer</span>
                  </p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Kata menyala bergantian mengikuti intonasi bicara narator (CapCut / TikTok Style), visual & audio tersinkronisasi 100%.
                  </p>
                </div>
              </label>

              {/* Mode B */}
              <label
                onClick={() => setRenderMode('compact_fixed')}
                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition ${
                  renderMode === 'compact_fixed'
                    ? 'border-cyan-500 bg-cyan-950/20'
                    : 'border-slate-800 bg-slate-950/40 hover:border-slate-700'
                }`}
              >
                <input
                  type="radio"
                  name="render_mode"
                  checked={renderMode === 'compact_fixed'}
                  onChange={() => setRenderMode('compact_fixed')}
                  className="mt-0.5 text-cyan-500 focus:ring-0 cursor-pointer"
                />
                <div>
                  <p className="text-xs font-semibold text-white">Mode B: Durasi Padat / Fixed</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Menargetkan durasi tetap per adegan dengan merapatkan jeda hening kosong narator.
                  </p>
                </div>
              </label>

              {/* Mode C */}
              <label
                onClick={() => setRenderMode('clean_no_text')}
                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition ${
                  renderMode === 'clean_no_text'
                    ? 'border-cyan-500 bg-cyan-950/20'
                    : 'border-slate-800 bg-slate-950/40 hover:border-slate-700'
                }`}
              >
                <input
                  type="radio"
                  name="render_mode"
                  checked={renderMode === 'clean_no_text'}
                  onChange={() => setRenderMode('clean_no_text')}
                  className="mt-0.5 text-cyan-500 focus:ring-0 cursor-pointer"
                />
                <div>
                  <p className="text-xs font-semibold text-white">Mode C: Clean Master (Tanpa Teks)</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Video bersih tanpa stiker teks, klip & audio sudah tersinkronisasi 100%, siap diedit manual.
                  </p>
                </div>
              </label>
            </div>

            {/* Pengaturan Visual, Kamera & Posisi Teks Pro */}
            <div className="pt-3 border-t border-slate-800/80 flex flex-col gap-3">
              {/* Posisi Vertikal Subtitle (Overlay Y) */}
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 font-medium flex items-center gap-1.5">
                    <MoveVertical className="w-3.5 h-3.5 text-cyan-400" />
                    Posisi Vertikal Teks (Y: {overlayY}px)
                  </span>
                  <div className="flex items-center gap-1">
                    {[
                      { label: 'Atas', y: 340 },
                      { label: 'Tengah', y: 920 },
                      { label: 'Bawah', y: 1380 },
                    ].map((preset) => (
                      <button
                        key={preset.label}
                        type="button"
                        onClick={() => handleProjectSettingChange({ overlay_y: preset.y })}
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold border transition cursor-pointer ${
                          Math.abs(overlayY - preset.y) < 60
                            ? 'bg-cyan-500/20 border-cyan-500 text-cyan-300'
                            : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-white'
                        }`}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>
                <input
                  type="range"
                  min="180"
                  max="1460"
                  step="10"
                  value={overlayY}
                  onChange={(e) => handleProjectSettingChange({ overlay_y: parseInt(e.target.value, 10) })}
                  className="w-full accent-cyan-400 cursor-pointer"
                />
              </div>

              {/* Gerak Kamera & Gaya Transisi */}
              <div className="grid grid-cols-2 gap-2.5 text-xs">
                <div>
                  <label className="text-[11px] text-slate-400 flex items-center gap-1 mb-1">
                    <Camera className="w-3 h-3 text-cyan-400" />
                    Gerak Kamera B-Roll
                  </label>
                  <select
                    value={cameraMotion}
                    onChange={(e) => handleProjectSettingChange({ camera_motion: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 cursor-pointer"
                  >
                    <option value="dynamic_zoom">Sinematik Drift / Push</option>
                    <option value="pan_drift">Pan Horizontal Halus</option>
                    <option value="static">Statis (Tanpa Gerak)</option>
                  </select>
                </div>

                <div>
                  <label className="text-[11px] text-slate-400 flex items-center gap-1 mb-1">
                    <Sparkles className="w-3 h-3 text-amber-400" />
                    Transisi Antar Klip
                  </label>
                  <select
                    value={transitionStyle}
                    onChange={(e) => handleProjectSettingChange({ transition_style: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 cursor-pointer"
                  >
                    <option value="clean_cut">Clean Cut (Tanpa Kedip)</option>
                    <option value="smooth_fade">Smooth Fade In/Out</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Trigger Button */}
            <button
              disabled={isRendering || !currentProject?.voiceover || currentProject?.scenes.length === 0}
              onClick={handleStartRender}
              className={`w-full py-3 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition shadow-lg ${
                isRendering || !currentProject?.voiceover || currentProject?.scenes.length === 0
                  ? 'bg-slate-800 text-slate-500 cursor-not-allowed shadow-none'
                  : 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 shadow-cyan-500/25 cursor-pointer'
              }`}
            >
              {isRendering ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Sedang Merender...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-slate-950" />
                  Proses & Render Video (FastStart MP4)
                </>
              )}
            </button>
          </div>

          {/* Render Progress, Live Subtitle Simulator & HTML5 Video Player */}
          <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800">
                <button
                  type="button"
                  onClick={() => setPreviewTab('live')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    previewTab === 'live'
                      ? 'bg-cyan-500 text-slate-950 shadow'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <Eye className="w-3.5 h-3.5" />
                  Live Simulasi Teks
                </button>
                <button
                  type="button"
                  onClick={() => setPreviewTab('video')}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    previewTab === 'video'
                      ? 'bg-cyan-500 text-slate-950 shadow'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <Video className="w-3.5 h-3.5" />
                  Hasil Render MP4
                </button>
              </div>
              {activeJob && (
                <span
                  className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                    activeJob.status === 'COMPLETED'
                      ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                      : activeJob.status === 'FAILED'
                      ? 'bg-rose-950 text-rose-400 border border-rose-800'
                      : 'bg-cyan-950 text-cyan-400 border border-cyan-800 animate-pulse'
                  }`}
                >
                  {activeJob.status}
                </span>
              )}
            </div>

            {/* Scene Selector untuk Live Simulasi */}
            {previewTab === 'live' && currentProject?.scenes && currentProject.scenes.length > 0 && (
              <div className="flex items-center justify-between gap-2 bg-slate-950/60 px-3 py-2 rounded-xl border border-slate-800/80 text-xs">
                <span className="text-slate-400">Pilih Adegan Simulasi:</span>
                <div className="flex items-center gap-1 flex-wrap">
                  {currentProject.scenes.map((sc, sIdx) => (
                    <button
                      key={sc.id}
                      type="button"
                      onClick={() => setPreviewSceneIdx(sIdx)}
                      className={`px-2 py-0.5 rounded text-[11px] font-bold transition cursor-pointer ${
                        previewSceneIdx === sIdx
                          ? 'bg-cyan-500 text-slate-950'
                          : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                      }`}
                    >
                      #{sIdx + 1}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Progress Bar (Visible while rendering) */}
            {isRendering && activeJob && (
              <div className="flex flex-col gap-2 bg-slate-950/60 p-3.5 rounded-xl border border-slate-800">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 font-medium">{activeJob.current_step || 'Memproses...'}</span>
                  <span className="text-cyan-400 font-mono font-bold">{activeJob.progress_percent}%</span>
                </div>
                <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                  <div
                    className="bg-gradient-to-r from-cyan-500 to-blue-500 h-full rounded-full transition-all duration-300"
                    style={{ width: `${activeJob.progress_percent}%` }}
                  />
                </div>
              </div>
            )}

            {/* Video Player / Live Interactive 9:16 Preview Container */}
            <div className="aspect-[9/16] max-h-[520px] w-full bg-slate-950 rounded-xl overflow-hidden border border-slate-800 flex items-center justify-center relative shadow-inner mx-auto">
              {previewTab === 'live' && currentProject?.scenes && currentProject.scenes.length > 0 ? (
                (() => {
                  const sc = currentProject.scenes[Math.min(previewSceneIdx, currentProject.scenes.length - 1)] || currentProject.scenes[0];
                  const accent = sc.accent_color_hex || '#38BDF8';
                  const rawScript = (sc.script_text || 'Contoh tampilan teks takarir dinamis dengan nyala per kata otomatis.').replace(/\[|\]/g, '');
                  // Pecah ke frasa pendek ~8 kata seperti mesin backend
                  const allWords = rawScript.split(/\s+/).filter(Boolean);
                  const phraseSize = 8;
                  const numPhrases = Math.max(1, Math.ceil(allWords.length / phraseSize));
                  const activeGlobalWord = karaokeTick % Math.max(1, allWords.length);
                  const activePhraseIdx = Math.min(numPhrases - 1, Math.floor(activeGlobalWord / phraseSize));
                  const phraseWords = allWords.slice(activePhraseIdx * phraseSize, (activePhraseIdx + 1) * phraseSize);
                  const activeLocalWord = activeGlobalWord - activePhraseIdx * phraseSize;
                  const topPercent = Math.max(8, Math.min(76, Math.round((overlayY / 1920) * 100)));

                  return (
                    <div className="w-full h-full relative bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900 flex flex-col items-center overflow-hidden select-none">
                      {/* Grid panduan halus 9:16 */}
                      <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:18px_18px] opacity-40" />
                      <div className="absolute top-3 left-3 right-3 flex items-center justify-between text-[10px] text-slate-400 bg-slate-950/80 px-2.5 py-1 rounded-lg border border-slate-800/80">
                        <span>Adegan #{previewSceneIdx + 1} • Frasa {activePhraseIdx + 1}/{numPhrases}</span>
                        <span className="text-cyan-400 font-mono">Y: {overlayY}px</span>
                      </div>

                      {/* Kartu Lencana + Subtitle Dinamis sesuai posisi overlayY */}
                      <div
                        className="absolute left-3 right-3 flex flex-col items-center gap-2 transition-all duration-150"
                        style={{ top: `${topPercent}%` }}
                      >
                        {sc.headline_text && (
                          <div
                            className="px-4 py-1 rounded-full bg-slate-950/95 text-white font-extrabold text-xs tracking-wide shadow-lg"
                            style={{
                              border: `2px solid ${accent}`,
                              boxShadow: `0 0 16px ${accent}55`,
                            }}
                          >
                            {sc.headline_text}
                          </div>
                        )}

                        {renderMode !== 'clean_no_text' && (
                          <div className="bg-[#080c16]/95 border border-white/15 rounded-2xl px-4 py-2.5 max-w-[92%] shadow-2xl text-center">
                            <p className="text-[13px] font-bold leading-snug flex flex-wrap items-center justify-center gap-x-1.5 gap-y-1">
                              {phraseWords.map((w, wIdx) => {
                                const isAct = wIdx === activeLocalWord;
                                return (
                                  <span
                                    key={wIdx}
                                    className={`inline-block transition-all duration-150 px-1 rounded ${
                                      isAct ? 'scale-110 -translate-y-0.5 font-extrabold' : 'text-white'
                                    }`}
                                    style={
                                      isAct
                                        ? {
                                            color: accent,
                                            backgroundColor: `${accent}22`,
                                            border: `1px solid ${accent}aa`,
                                            textShadow: '0 2px 4px rgba(0,0,0,0.95)',
                                          }
                                        : { textShadow: '0 2px 4px rgba(0,0,0,0.95)' }
                                    }
                                  >
                                    {w}
                                  </span>
                                );
                              })}
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()
              ) : activeJob?.status === 'COMPLETED' && activeJob.output_video_url ? (
                <video
                  controls
                  autoPlay
                  loop
                  playsInline
                  src={`${API_BASE}${activeJob.output_video_url}`}
                  className="w-full h-full object-contain bg-black"
                />
              ) : (
                <div className="text-center p-6 flex flex-col items-center gap-3 text-slate-500">
                  <div className="w-12 h-12 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-400">
                    <Video className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-slate-400">Belum Ada Video Hasil Render</p>
                    <p className="text-[11px] text-slate-500 mt-1 max-w-[220px]">
                      Gunakan tab "Live Simulasi Teks" di atas atau klik "Proses & Render Video" untuk menghasilkan MP4.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Download Button */}
            {activeJob?.status === 'COMPLETED' && activeJob.output_video_url && (
              <a
                href={`${API_BASE}${activeJob.output_video_url}`}
                download="autosync_video.mp4"
                className="w-full py-2.5 px-4 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs rounded-xl flex items-center justify-center gap-2 transition shadow-md shadow-emerald-500/20"
              >
                <Download className="w-4 h-4" />
                Unduh Video Hasil (1080x1920 MP4)
              </a>
            )}
          </div>
        </div>
      </main>

      {/* Modal Gemini API Key */}
      {showApiModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl flex flex-col gap-4">
            <div className="flex items-center gap-2 text-white">
              <Key className="w-5 h-5 text-amber-400" />
              <h3 className="text-base font-bold">Google Gemini API Key</h3>
            </div>
            <p className="text-xs text-slate-400">
              Digunakan untuk <strong>AI Vision Multimodal Matching</strong>: AI mengekstrak dan menganalisis frame isi video secara visual untuk dicocokkan otomatis ke naskah adegan.
            </p>

            <div>
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-300">Gemini API Key (Vision & Storyteller)</label>
                <a
                  href="https://aistudio.google.com/app/apikey"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[11px] text-cyan-400 hover:text-cyan-300 underline inline-flex items-center gap-1 cursor-pointer"
                >
                  Dapatkan Gratis di Google AI Studio ↗
                </a>
              </div>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Tempel Gemini API Key di sini (AIzaSy...)"
                className="w-full mt-1.5 bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
              />
              {apiKey ? (
                <p className="text-[11px] text-emerald-400 mt-1.5 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  API Key terisi & siap terhubung ke model Gemini 2.5 Flash & Flash-Lite!
                </p>
              ) : (
                <p className="text-[11px] text-amber-400/90 mt-1.5 flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  Belum ada API Key. Tempelkan kunci API gratis Anda di atas.
                </p>
              )}
            </div>

            <div className="pt-2 border-t border-slate-800/80">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-300">Groq API Key (Opsional - Whisper STT)</label>
                <a
                  href="https://console.groq.com/keys"
                  target="_blank"
                  rel="noreferrer"
                  className="text-[10px] text-cyan-400 hover:text-cyan-300 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800 inline-flex items-center gap-1 cursor-pointer"
                >
                  Dapatkan Gratis di Groq ↗
                </a>
              </div>
              <input
                type="password"
                value={groqApiKey}
                onChange={(e) => setGroqApiKey(e.target.value)}
                placeholder="gsk_... (Opsional untuk transkripsi super cepat 0.5s)"
                className="w-full mt-1.5 bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
              />
              {groqApiKey ? (
                <p className="text-[11px] text-emerald-400 mt-1.5 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Groq Whisper Large-v3 aktif (transkripsi kata super cepat).
                </p>
              ) : (
                <p className="text-[11px] text-slate-400 mt-1.5">
                  Opsional: Groq menyediakan Whisper-Large-v3 super cepat (0.5s) dengan kuota ribuan request gratis.
                </p>
              )}
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={handleSaveApiKeys}
                className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-xs rounded-xl transition cursor-pointer"
              >
                Simpan & Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Buat Proyek Baru */}
      {showNewModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl flex flex-col gap-4">
            <h3 className="text-base font-bold text-white">Buat Proyek Baru</h3>
            <p className="text-xs text-slate-400">
              Beri judul proyek untuk video pendek vertikal Anda (TikTok / Reels / Shorts).
            </p>

            <div>
              <label className="text-xs font-semibold text-slate-300">Judul Proyek</label>
              <input
                type="text"
                autoFocus
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Contoh: Edukasi Jejak Digital"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCreateProject();
                }}
                className="w-full mt-1.5 bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setShowNewModal(false)}
                className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-white transition cursor-pointer"
              >
                Batal
              </button>
              <button
                type="button"
                disabled={loading || !newTitle.trim()}
                onClick={handleCreateProject}
                className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 disabled:bg-slate-800 disabled:text-slate-500 text-slate-950 font-semibold text-xs rounded-xl transition cursor-pointer"
              >
                Buat Proyek
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
