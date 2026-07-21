import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store/useStore'
import { Search, Video, Camera, Play, Square, RefreshCw, Layers } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'

export const CommandPalette: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const { addNotification } = useStore()
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setIsOpen((prev) => !prev)
      } else if (e.key === 'Escape') {
        setIsOpen(false)
      }
    }
    
    const handleOpenEvent = () => setIsOpen(true)

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('open-command-palette', handleOpenEvent)
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('open-command-palette', handleOpenEvent)
    }
  }, [])

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50)
      setQuery('')
    }
  }, [isOpen])

  const actions = [
    { id: 'nav-dash', name: 'Go to Dashboard', category: 'Navigation', icon: <Layers className="h-4 w-4" />, action: () => { navigate('/'); setIsOpen(false) } },
    { id: 'nav-live', name: 'Go to Live Stream', category: 'Navigation', icon: <Video className="h-4 w-4" />, action: () => { navigate('/live'); setIsOpen(false) } },
    { id: 'nav-recs', name: 'Go to Recordings', category: 'Navigation', icon: <Play className="h-4 w-4" />, action: () => { navigate('/recordings'); setIsOpen(false) } },
    { id: 'act-snap', name: 'Capture Snapshot Now', category: 'Actions', icon: <Camera className="h-4 w-4" />, action: async () => {
        setIsOpen(false)
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
    },
    { id: 'act-rec-start', name: 'Start Manual Recording', category: 'Actions', icon: <Play className="h-4 w-4 text-emerald-400" />, action: async () => {
        setIsOpen(false)
        try {
          const res = await fetch('/recording/start', { method: 'POST' })
          if (res.ok) {
            addNotification('Manual recording started', 'success')
          }
        } catch {
          addNotification('Failed to start recording', 'error')
        }
      } 
    },
    { id: 'act-rec-stop', name: 'Stop Manual Recording', category: 'Actions', icon: <Square className="h-4 w-4 text-rose-400" />, action: async () => {
        setIsOpen(false)
        try {
          const res = await fetch('/recording/stop', { method: 'POST' })
          if (res.ok) {
            addNotification('Recording stopped & finalizing', 'success')
          }
        } catch {
          addNotification('Failed to stop recording', 'error')
        }
      } 
    },
    { id: 'act-restart', name: 'Restart Camera Feed', category: 'Actions', icon: <RefreshCw className="h-4 w-4 text-amber-400" />, action: async () => {
        setIsOpen(false)
        addNotification('Restarting camera...', 'warning')
        try {
          const res = await fetch('/camera/restart', { method: 'POST' })
          if (res.ok) {
            addNotification('Camera restarted successfully', 'success')
          }
        } catch {
          addNotification('Failed to restart camera', 'error')
        }
      } 
    },
  ]

  const filtered = actions.filter((act) =>
    act.name.toLowerCase().includes(query.toLowerCase()) ||
    act.category.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsOpen(false)}
            className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm"
          />

          {/* Palette Box */}
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: -10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: -10 }}
            transition={{ duration: 0.15 }}
            className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-slate-900 bg-slate-950 shadow-2xl"
          >
            {/* Input */}
            <div className="flex items-center gap-3 border-b border-slate-900 px-4 py-3.5">
              <Search className="h-5 w-5 text-slate-500" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Type a command or action..."
                className="flex-1 bg-transparent text-sm text-slate-200 placeholder-slate-500 outline-none"
              />
              <kbd className="hidden sm:inline-block rounded bg-slate-900 border border-slate-800 px-2 py-0.5 text-[10px] text-slate-400 font-mono">
                ESC
              </kbd>
            </div>

            {/* List */}
            <div className="max-h-[300px] overflow-y-auto p-2">
              {filtered.length > 0 ? (
                <div className="space-y-1">
                  {filtered.map((item) => (
                    <button
                      key={item.id}
                      onClick={item.action}
                      className="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs font-medium text-slate-400 hover:bg-slate-900 hover:text-slate-100 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-slate-500">{item.icon}</span>
                        <span>{item.name}</span>
                      </div>
                      <span className="text-[10px] tracking-wider uppercase text-slate-600 bg-slate-950 border border-slate-900 px-2 py-0.5 rounded-md">
                        {item.category}
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="py-12 text-center text-xs text-slate-600">
                  No matching actions or navigation targets found.
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
