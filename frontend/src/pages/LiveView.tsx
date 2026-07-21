import React, { useState } from 'react'
import { useStore } from '../store/useStore'
import {
  Video,
  Camera,
  Play,
  Square,
  ZoomIn,
  ZoomOut,
  Grid,
  RefreshCw,
  Info,
} from 'lucide-react'

export const LiveView: React.FC = () => {
  const { health, addNotification } = useStore()
  const [zoom, setZoom] = useState(1)
  const [showGrid, setShowGrid] = useState(false)
  const [streamUrl, setStreamUrl] = useState('/stream.mjpeg')
  const [streamError, setStreamError] = useState(false)

  const handleZoom = (direction: 'in' | 'out') => {
    if (direction === 'in' && zoom < 4) setZoom(zoom + 0.5)
    if (direction === 'out' && zoom > 1) setZoom(zoom - 0.5)
  }

  const handleSnapshot = async () => {
    addNotification('Triggering snapshot...', 'info')
    try {
      const res = await fetch('/snapshot')
      if (res.ok) {
        addNotification('Snapshot saved successfully', 'success')
      }
    } catch {
      addNotification('Failed to capture snapshot', 'error')
    }
  }

  const handleRecordingToggle = async () => {
    const active = health?.recording?.active || false
    const endpoint = active ? '/recording/stop' : '/recording/start'
    const successMsg = active ? 'Manual recording stopped' : 'Manual recording started'
    try {
      const res = await fetch(endpoint, { method: 'POST' })
      if (res.ok) {
        addNotification(successMsg, 'success')
      }
    } catch {
      addNotification('Failed to toggle recording state', 'error')
    }
  }

  const reconnectStream = () => {
    setStreamError(false)
    setStreamUrl(`/stream.mjpeg?t=${Date.now()}`)
  }

  const recordingActive = health?.recording?.active || false

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-100">Live Camera Feed</h1>
          <p className="text-sm text-slate-500">Low-latency live stream with hardware control widgets.</p>
        </div>

        {/* Connection health indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-xs shrink-0">
          <span className={`h-2 w-2 rounded-full ${streamError ? 'bg-rose-500 animate-pulse' : 'bg-emerald-500 animate-pulse'}`} />
          <span className="font-semibold text-slate-300">{streamError ? 'Reconnecting' : 'Connected'}</span>
        </div>
      </div>

      {/* Main Viewport Container */}
      <div className="relative flex flex-col xl:flex-row gap-6">
        {/* Stream Area */}
        <div className="flex-1 flex flex-col gap-4">
          <div
            id="live-viewport"
            className="relative rounded-2xl border border-slate-900 bg-slate-950 overflow-hidden shadow-2xl aspect-video"
          >
            {/* Stream Image */}
            {!streamError ? (
              <img
                src={streamUrl}
                alt="Live Surveillance Feed"
                onError={() => setStreamError(true)}
                style={{ transform: `scale(${zoom})`, transformOrigin: 'center' }}
                className="h-full w-full object-cover transition-transform duration-200"
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-slate-950/90 text-slate-400">
                <Video className="h-12 w-12 text-slate-700 animate-pulse" />
                <div className="text-center">
                  <p className="text-sm font-semibold text-slate-200">Stream Connection Offline</p>
                  <p className="text-xs text-slate-600 mt-1">Failed to connect to backend stream controller.</p>
                </div>
                <button
                  onClick={reconnectStream}
                  className="flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-850 text-slate-200"
                >
                  <RefreshCw className="h-4 w-4" />
                  Retry Connection
                </button>
              </div>
            )}

            {/* Viewport Grid Overlay */}
            {showGrid && !streamError && (
              <div className="absolute inset-0 grid grid-cols-3 grid-rows-3 pointer-events-none">
                <div className="border-r border-b border-dashed border-emerald-500/20" />
                <div className="border-r border-b border-dashed border-emerald-500/20" />
                <div className="border-b border-dashed border-emerald-500/20" />
                <div className="border-r border-b border-dashed border-emerald-500/20" />
                <div className="border-r border-b border-dashed border-emerald-500/20" />
                <div className="border-b border-dashed border-emerald-500/20" />
                <div className="border-r border-dashed border-emerald-500/20" />
                <div className="border-r border-dashed border-emerald-500/20" />
                <div className="pointer-events-none" />
              </div>
            )}

            {/* Text Overlays on Video */}
            {!streamError && (
              <div className="absolute bottom-4 left-4 flex flex-wrap gap-2 pointer-events-none">
                <span className="px-2.5 py-1 rounded-full bg-slate-950/80 border border-slate-900 text-[10px] text-slate-300 font-mono backdrop-blur-sm">
                  RES: {health?.recording?.active ? health.recording.path ? '640x480' : '640x480' : '640x480'}
                </span>
                <span className="px-2.5 py-1 rounded-full bg-slate-950/80 border border-slate-900 text-[10px] text-emerald-400 font-mono backdrop-blur-sm">
                  FPS: {health?.pipeline?.streaming_fps?.toFixed(1) || '0.0'}
                </span>
                <span className="px-2.5 py-1 rounded-full bg-slate-950/80 border border-slate-900 text-[10px] text-slate-300 font-mono backdrop-blur-sm">
                  LAT: {health?.pipeline?.avg_latency_ms?.toFixed(0) || '0'} ms
                </span>
              </div>
            )}
          </div>

          {/* Stream Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-2xl border border-slate-900 bg-slate-950/40">
            <div className="flex items-center gap-2">
              <button
                onClick={handleRecordingToggle}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold shadow-md transition-all ${
                  recordingActive
                    ? 'bg-rose-500 hover:bg-rose-600 text-slate-950 shadow-rose-500/10'
                    : 'bg-emerald-500 hover:bg-emerald-600 text-slate-950 shadow-emerald-500/10'
                }`}
              >
                {recordingActive ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                {recordingActive ? 'Stop Recording' : 'Start Recording'}
              </button>

              <button
                onClick={handleSnapshot}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-850 text-xs font-semibold text-slate-200 transition-colors"
              >
                <Camera className="h-4 w-4" />
                Snapshot
              </button>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setShowGrid(!showGrid)}
                className={`p-2.5 rounded-xl border transition-all ${
                  showGrid ? 'bg-slate-900 border-slate-800 text-emerald-400' : 'bg-transparent border-transparent text-slate-500 hover:text-slate-200'
                }`}
                title="Toggle View Grid"
              >
                <Grid className="h-4 w-4" />
              </button>

              <button
                onClick={() => handleZoom('in')}
                className="p-2.5 rounded-xl bg-slate-900/40 hover:bg-slate-900 text-slate-400 hover:text-slate-200 transition-colors"
                title="Zoom In"
              >
                <ZoomIn className="h-4 w-4" />
              </button>
              <span className="text-xs font-mono font-bold text-slate-400 w-8 text-center">{zoom.toFixed(1)}x</span>
              <button
                onClick={() => handleZoom('out')}
                className="p-2.5 rounded-xl bg-slate-900/40 hover:bg-slate-900 text-slate-400 hover:text-slate-200 transition-colors"
                title="Zoom Out"
              >
                <ZoomOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Info panel */}
        <div className="w-full xl:w-80 p-5 rounded-2xl border border-slate-900 bg-slate-950/40 flex flex-col gap-4">
          <div className="flex items-center gap-2 border-b border-slate-900 pb-3">
            <Info className="h-4 w-4 text-slate-500" />
            <span className="text-sm font-semibold text-slate-200">Stream Diagnostic</span>
          </div>

          <div className="space-y-3.5 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Video Container</span>
              <span className="font-semibold text-slate-300 font-mono">MJPEG / MP4</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Capture Engine</span>
              <span className="font-semibold text-slate-300">LatestBuffer Atomic</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Auto Reconnection</span>
              <span className="font-semibold text-slate-300">Active (Auto-Reload)</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Network Host</span>
              <span className="font-semibold text-slate-300 font-mono">127.0.0.1:8000</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
