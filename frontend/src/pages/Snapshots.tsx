import React, { useState, useEffect } from 'react'
import { useStore } from '../store/useStore'
import { Camera, Download, Trash2, X, Eye } from 'lucide-react'

export const Snapshots: React.FC = () => {
  const { addNotification } = useStore()
  const [snapshots, setSnapshots] = useState<string[]>([])
  const [selectedSnap, setSelectedSnap] = useState<string | null>(null)

  const fetchSnapshots = async () => {
    try {
      const res = await fetch('/snapshots')
      if (res.ok) {
        const data = await res.json()
        setSnapshots(data)
      }
    } catch (err) {
      console.error('Failed to fetch snapshots:', err)
    }
  }

  useEffect(() => {
    fetchSnapshots()
  }, [])

  const handleDelete = async (name: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Are you sure you want to delete this snapshot?')) return
    try {
      const res = await fetch(`/snapshots/${name}`, { method: 'DELETE' })
      if (res.ok) {
        addNotification('Snapshot deleted', 'success')
        fetchSnapshots()
      }
    } catch {
      addNotification('Failed to delete snapshot', 'error')
    }
  }

  const formatSnapshotName = (name: string) => {
    // snapshot_20260721_101722.jpg
    const parts = name.replace('.jpg', '').split('_')
    if (parts.length < 3) return name
    const dateStr = parts[1]
    const timeStr = parts[2]
    
    const yr = dateStr.slice(0, 4)
    const mo = dateStr.slice(4, 6)
    const dy = dateStr.slice(6, 8)
    
    const hr = timeStr.slice(0, 2)
    const mn = timeStr.slice(2, 4)
    const sc = timeStr.slice(4, 6)
    
    return `${yr}-${mo}-${dy} ${hr}:${mn}:${sc}`
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-100">Camera Snapshots</h1>
          <p className="text-sm text-slate-500">View and manage captured high-resolution snapshot images.</p>
        </div>
      </div>

      {/* Grid */}
      {snapshots.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-6">
          {snapshots.map((name) => (
            <div
              key={name}
              onClick={() => setSelectedSnap(name)}
              className="group relative aspect-video rounded-2xl border border-slate-900 bg-slate-950/40 hover:border-slate-800 transition-all cursor-pointer overflow-hidden shadow-xl"
            >
              <img
                src={`/snapshots/${name}`}
                alt={name}
                className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-200"
              />
              
              {/* Hover overlay controls */}
              <div className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                <button
                  onClick={() => setSelectedSnap(name)}
                  className="p-2 rounded-xl bg-slate-950/80 border border-slate-900 text-slate-200 hover:text-emerald-400 transition-colors shadow-md"
                  title="Preview"
                >
                  <Eye className="h-4.5 w-4.5" />
                </button>
                <a
                  href={`/snapshots/${name}`}
                  download={name}
                  onClick={(e) => e.stopPropagation()}
                  className="p-2 rounded-xl bg-slate-950/80 border border-slate-900 text-slate-200 hover:text-emerald-400 transition-colors shadow-md"
                  title="Download"
                >
                  <Download className="h-4.5 w-4.5" />
                </a>
                <button
                  onClick={(e) => handleDelete(name, e)}
                  className="p-2 rounded-xl bg-slate-950/80 border border-slate-900 text-slate-200 hover:text-rose-400 transition-colors shadow-md"
                  title="Delete"
                >
                  <Trash2 className="h-4.5 w-4.5" />
                </button>
              </div>

              {/* Timestamp label footer */}
              <div className="absolute bottom-2 left-2 px-2.5 py-1 rounded bg-slate-950/85 text-[10px] text-slate-300 font-mono font-medium shadow-md">
                {formatSnapshotName(name)}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="py-24 rounded-2xl border border-slate-900 border-dashed text-center text-slate-500 text-xs flex flex-col items-center justify-center gap-3">
          <Camera className="h-8 w-8 text-slate-700" />
          <span>No snapshots taken yet. Use Quick Actions to capture one.</span>
        </div>
      )}

      {/* Preview Modal */}
      {selectedSnap && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => setSelectedSnap(null)} />
          <div className="relative max-w-4xl w-full rounded-2xl border border-slate-900 bg-slate-950 overflow-hidden shadow-2xl z-10">
            <button
              onClick={() => setSelectedSnap(null)}
              className="absolute right-4 top-4 p-1.5 rounded-full bg-slate-950/80 border border-slate-900 text-slate-400 hover:text-slate-200 transition-colors z-20"
            >
              <X className="h-4 w-4" />
            </button>
            <div className="p-4 bg-slate-950">
              <img
                src={`/snapshots/${selectedSnap}`}
                alt={selectedSnap}
                className="w-full h-auto max-h-[70vh] object-contain rounded-lg"
              />
              <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
                <span className="font-semibold text-slate-300">{formatSnapshotName(selectedSnap)}</span>
                <a
                  href={`/snapshots/${selectedSnap}`}
                  download={selectedSnap}
                  className="flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-slate-850 rounded-xl border border-slate-800 text-slate-200 font-semibold"
                >
                  <Download className="h-4 w-4" />
                  Download Image
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
