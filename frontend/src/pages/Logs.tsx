import React, { useState, useEffect, useRef } from 'react'
import { useStore } from '../store/useStore'
import { Terminal, Pause, Play, Copy, Download, Search } from 'lucide-react'

export const Logs: React.FC = () => {
  const { logs, fetchLogs, addNotification } = useStore()
  const [filterLevel, setFilterLevel] = useState<'ALL' | 'INFO' | 'WARNING' | 'ERROR'>('ALL')
  const [search, setSearch] = useState('')
  const [paused, setPaused] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const consoleRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchLogs()
    if (paused) return
    const timer = setInterval(fetchLogs, 3000)
    return () => clearInterval(timer)
  }, [paused])

  useEffect(() => {
    if (autoScroll && consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const getFilteredLogs = () => {
    let result = [...logs]
    
    if (filterLevel !== 'ALL') {
      result = result.filter((line) => line.toUpperCase().includes(filterLevel))
    }
    
    if (search) {
      result = result.filter((line) => line.toLowerCase().includes(search.toLowerCase()))
    }
    
    return result
  }

  const filtered = getFilteredLogs()

  const copyToClipboard = () => {
    const text = logs.join('')
    navigator.clipboard.writeText(text)
    addNotification('Logs copied to clipboard', 'success')
  }

  const downloadLogs = () => {
    const text = logs.join('')
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `camera_logs_${new Date().toISOString()}.txt`
    a.click()
    URL.revokeObjectURL(url)
    addNotification('Logs downloaded', 'success')
  }

  const getLineColor = (line: string) => {
    const upper = line.toUpperCase()
    if (upper.includes('ERROR') || upper.includes('CRITICAL')) return 'text-rose-400 font-bold'
    if (upper.includes('WARNING') || upper.includes('WARN')) return 'text-amber-400 font-semibold'
    if (upper.includes('INFO')) return 'text-slate-300'
    if (upper.includes('DEBUG')) return 'text-slate-500'
    return 'text-slate-400'
  }

  return (
    <div className="flex flex-col gap-6 h-full">
      {/* Header Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-100">System Logs</h1>
          <p className="text-sm text-slate-500">Live scrolling logger from CAMZ camera background services.</p>
        </div>

        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search logs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 w-full sm:w-40 rounded-xl bg-slate-900/50 border border-slate-900 pl-9 pr-4 text-xs text-slate-300 placeholder-slate-500 focus:outline-none focus:border-slate-800"
            />
          </div>

          <div className="flex items-center gap-1.5 rounded-xl bg-slate-900 border border-slate-900 p-1">
            {(['ALL', 'INFO', 'WARNING', 'ERROR'] as const).map((lvl) => (
              <button
                key={lvl}
                onClick={() => setFilterLevel(lvl)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase transition-all ${
                  filterLevel === lvl ? 'bg-slate-800 text-emerald-400' : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setPaused(!paused)}
              className="p-2 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-850 text-slate-400 hover:text-slate-200 transition-colors"
              title={paused ? 'Resume Polling' : 'Pause Polling'}
            >
              {paused ? <Play className="h-4 w-4 text-emerald-400 animate-pulse" /> : <Pause className="h-4 w-4" />}
            </button>
            <button
              onClick={copyToClipboard}
              className="p-2 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-850 text-slate-400 hover:text-slate-200 transition-colors"
              title="Copy to Clipboard"
            >
              <Copy className="h-4 w-4" />
            </button>
            <button
              onClick={downloadLogs}
              className="p-2 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-850 text-slate-400 hover:text-slate-200 transition-colors"
              title="Download Logs"
            >
              <Download className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Log Console Terminal */}
      <div
        ref={consoleRef}
        className="flex-1 min-h-64 overflow-y-auto rounded-2xl border border-slate-900 bg-[#020617] p-5 font-mono text-xs leading-relaxed space-y-1 shadow-2xl"
      >
        <div className="text-[10px] text-slate-700 select-none pb-2 border-b border-slate-900 mb-3 flex items-center justify-between">
          <span>LOGGER TERMINAL CONNECTED (POLLING EVERY 3S)</span>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="accent-emerald-500 rounded bg-slate-900 border-slate-800"
              />
              Auto-Scroll
            </label>
          </div>
        </div>

        {filtered.length > 0 ? (
          filtered.map((line, idx) => (
            <div key={idx} className="hover:bg-slate-900/30 px-1 py-0.5 rounded break-all whitespace-pre-wrap">
              <span className="text-slate-600 mr-3 select-none">{(idx + 1).toString().padStart(4, '0')}</span>
              <span className={getLineColor(line)}>{line.replace('\n', '')}</span>
            </div>
          ))
        ) : (
          <div className="h-full flex items-center justify-center text-slate-600 text-xs gap-2 py-24 select-none">
            <Terminal className="h-4 w-4 animate-pulse" />
            <span>Console buffer is empty or matches no filters.</span>
          </div>
        )}
      </div>
    </div>
  )
}
