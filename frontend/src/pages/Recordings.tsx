import React, { useState, useEffect } from 'react'
import { useStore } from '../store/useStore'
import {
  Play,
  Download,
  Trash2,
  Calendar,
  HardDrive,
  Info,
  X,
  Search,
} from 'lucide-react'

export const Recordings: React.FC = () => {
  const { recordings, fetchRecordings, addNotification } = useStore()
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState<'date' | 'duration' | 'size'>('date')
  const [selectedRec, setSelectedRec] = useState<any | null>(null)

  useEffect(() => {
    fetchRecordings()
  }, [])

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Are you sure you want to delete this recording?')) return
    try {
      const res = await fetch(`/recordings/${id}`, { method: 'DELETE' })
      if (res.ok) {
        addNotification('Recording deleted successfully', 'success')
        fetchRecordings()
      }
    } catch {
      addNotification('Failed to delete recording', 'error')
    }
  }

  const getFilteredRecordings = () => {
    let result = [...recordings]
    if (search) {
      result = result.filter(
        (r) =>
          r.id.toLowerCase().includes(search.toLowerCase()) ||
          r.codec.toLowerCase().includes(search.toLowerCase())
      )
    }
    if (sortBy === 'date') {
      result.sort((a, b) => b.start_time.localeCompare(a.start_time))
    } else if (sortBy === 'duration') {
      result.sort((a, b) => b.duration_seconds - a.duration_seconds)
    } else if (sortBy === 'size') {
      result.sort((a, b) => b.file_size_bytes - a.file_size_bytes)
    }
    return result
  }

  const filtered = getFilteredRecordings()

  const formatSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-100">Media Recordings</h1>
          <p className="text-sm text-slate-500">View, play, and download recorded video sessions.</p>
        </div>

        {/* Filter controls */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-full sm:w-auto">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search by ID or codec..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 w-full sm:w-48 rounded-xl bg-slate-900/50 border border-slate-900 pl-9 pr-4 text-xs text-slate-300 placeholder-slate-500 focus:outline-none focus:border-slate-800"
            />
          </div>

          <div className="flex items-center gap-2 rounded-xl bg-slate-900 border border-slate-900 p-1">
            <button
              onClick={() => setSortBy('date')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                sortBy === 'date' ? 'bg-slate-800 text-emerald-400' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              Date
            </button>
            <button
              onClick={() => setSortBy('duration')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                sortBy === 'duration' ? 'bg-slate-800 text-emerald-400' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              Duration
            </button>
            <button
              onClick={() => setSortBy('size')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                sortBy === 'size' ? 'bg-slate-800 text-emerald-400' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              Size
            </button>
          </div>
        </div>
      </div>

      {/* Media Grid */}
      {filtered.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-6">
          {filtered.map((rec) => (
            <div
              key={rec.id}
              onClick={() => setSelectedRec(rec)}
              className="group relative rounded-2xl border border-slate-900 bg-slate-950/40 hover:bg-slate-900/40 hover:border-slate-800 transition-all cursor-pointer overflow-hidden shadow-xl"
            >
              {/* Thumbnail Container */}
              <div className="relative aspect-video bg-slate-950 overflow-hidden border-b border-slate-900">
                <img
                  src={`/recordings/${rec.id}/thumbnail`}
                  alt={`Thumbnail for ${rec.id}`}
                  className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-200"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none'
                  }}
                />
                <div className="absolute inset-0 bg-slate-950/20 group-hover:bg-slate-950/0 transition-colors flex items-center justify-center">
                  <div className="h-10 w-10 rounded-full bg-slate-950/80 border border-slate-900 flex items-center justify-center text-slate-200 opacity-0 group-hover:opacity-100 scale-90 group-hover:scale-100 transition-all shadow-lg">
                    <Play className="h-5 w-5 fill-slate-200" />
                  </div>
                </div>

                <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-slate-950/80 text-[10px] text-slate-300 font-mono">
                  {rec.duration_seconds}s
                </div>
              </div>

              {/* Summary details */}
              <div className="p-4 flex flex-col gap-2">
                <div className="flex items-center justify-between text-[10px] text-slate-500 font-semibold uppercase tracking-wider">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5" />
                    {new Date(rec.start_time).toLocaleDateString()}
                  </span>
                  <span>{rec.resolution}</span>
                </div>

                <h3 className="text-xs font-bold text-slate-300 line-clamp-1 truncate" title={rec.id}>
                  {rec.id}
                </h3>

                <div className="flex items-center justify-between border-t border-slate-900/50 pt-2 text-[10px] text-slate-500">
                  <span className="flex items-center gap-1">
                    <HardDrive className="h-3.5 w-3.5" />
                    {formatSize(rec.file_size_bytes)}
                  </span>

                  <button
                    onClick={(e) => handleDelete(rec.id, e)}
                    className="p-1 text-slate-500 hover:text-rose-400 rounded-lg hover:bg-slate-900 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="py-24 rounded-2xl border border-slate-900 border-dashed text-center text-slate-500 text-xs flex flex-col items-center justify-center gap-3">
          <Play className="h-8 w-8 text-slate-700" />
          <span>No recordings found matching your filters.</span>
        </div>
      )}

      {/* Playback Modal */}
      {selectedRec && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setSelectedRec(null)} />

          {/* Modal Container */}
          <div className="relative w-full max-w-4xl rounded-2xl border border-slate-900 bg-slate-950 overflow-hidden shadow-2xl z-10 flex flex-col lg:flex-row">
            {/* Close Button */}
            <button
              onClick={() => setSelectedRec(null)}
              className="absolute right-4 top-4 z-20 p-1.5 rounded-full bg-slate-950/80 border border-slate-900 text-slate-400 hover:text-slate-200 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>

            {/* Video Player */}
            <div className="flex-1 bg-black aspect-video flex items-center justify-center">
              <video
                src={`/recordings/${selectedRec.id}`}
                controls
                autoPlay
                className="h-full w-full object-contain"
              />
            </div>

            {/* Metadata Drawer */}
            <div className="w-full lg:w-80 border-t lg:border-t-0 lg:border-l border-slate-900 p-6 flex flex-col gap-6 text-xs text-slate-400 bg-slate-950/50">
              <div className="flex items-center gap-2 border-b border-slate-900 pb-3">
                <Info className="h-4 w-4 text-slate-500" />
                <span className="text-sm font-semibold text-slate-200">Session Metadata</span>
              </div>

              <div className="space-y-4">
                <div>
                  <div className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mb-1">
                    Recording ID
                  </div>
                  <div className="font-bold text-slate-200 select-all truncate break-all">{selectedRec.id}</div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mb-1 block">
                      Duration
                    </span>
                    <span className="text-slate-200 font-mono">{selectedRec.duration_seconds}s</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mb-1 block">
                      File Size
                    </span>
                    <span className="text-slate-200 font-mono">{formatSize(selectedRec.file_size_bytes)}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mb-1 block">
                      Average FPS
                    </span>
                    <span className="text-slate-200 font-mono">{selectedRec.average_fps} FPS</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mb-1 block">
                      Resolution
                    </span>
                    <span className="text-slate-200 font-mono">{selectedRec.resolution}</span>
                  </div>
                </div>

                <div className="border-t border-slate-900/50 pt-4 flex gap-2">
                  <a
                    href={`/recordings/${selectedRec.id}`}
                    download={`${selectedRec.id}.mp4`}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-850 text-slate-200 transition-colors"
                  >
                    <Download className="h-4 w-4" />
                    Download Video
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
