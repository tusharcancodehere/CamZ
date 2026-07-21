import React, { useState, useEffect } from 'react'
import { useStore } from '../store/useStore'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts'
import { BarChart3, TrendingUp, Cpu, Activity } from 'lucide-react'

export const Analytics: React.FC = () => {
  const { health } = useStore()
  const [range, setRange] = useState<'1h' | '6h' | '24h' | '7d'>('1h')
  const [liveHistory, setLiveHistory] = useState<any[]>([])

  // Store rolling history of live system metrics
  useEffect(() => {
    if (health) {
      const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      setLiveHistory((prev) => {
        const next = [
          ...prev,
          {
            time: now,
            cpu: health.system?.cpu_percent || 0,
            ram: health.system?.memory_percent || 0,
            fps: health.pipeline?.streaming_fps || 0,
          },
        ]
        if (next.length > 15) next.shift() // Keep last 15 ticks
        return next
      })
    }
  }, [health])

  // Mock static historical curves for selected range
  const getHistoricalData = () => {
    const data = []
    const points = range === '1h' ? 12 : range === '6h' ? 24 : range === '24h' ? 24 : 7
    const label = range === '1h' ? 'm' : range === '7d' ? ' Day' : ':00'

    for (let i = points; i > 0; i--) {
      data.push({
        name: range === '7d' ? `Day ${8 - i}` : `${12 - i}${label}`,
        motionEvents: Math.floor(Math.random() * 15) + 2,
        gbWritten: parseFloat((Math.random() * 2.5 + 0.1).toFixed(2)),
      })
    }
    return data
  }

  const histData = getHistoricalData()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-100">Performance Analytics</h1>
          <p className="text-sm text-slate-500">Live profiling of stream latency, CPU load, and system resources.</p>
        </div>

        {/* Range Selector */}
        <div className="flex items-center gap-1.5 rounded-xl bg-slate-900 border border-slate-900 p-1">
          {(['1h', '6h', '24h', '7d'] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase transition-all ${
                range === r ? 'bg-slate-800 text-emerald-400' : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Real-time System Load Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Live CPU & RAM Area Chart */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/40 flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-slate-500" />
            <span className="text-sm font-semibold text-slate-200">Live Resource Load (CPU / Memory %)</span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={liveHistory}>
                <defs>
                  <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorRam" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" stroke="#475569" fontSize={9} />
                <YAxis stroke="#475569" fontSize={9} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#020617', border: '1px solid #1e293b', borderRadius: '12px' }}
                />
                <Area type="monotone" dataKey="cpu" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorCpu)" name="CPU %" />
                <Area type="monotone" dataKey="ram" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorRam)" name="RAM %" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Live Streaming Frame Rate Chart */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/40 flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-emerald-400" />
            <span className="text-sm font-semibold text-slate-200">Live Streaming Frame Rate (FPS)</span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={liveHistory}>
                <defs>
                  <linearGradient id="colorFps" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#34d399" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#34d399" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" stroke="#475569" fontSize={9} />
                <YAxis stroke="#475569" fontSize={9} domain={[0, 30]} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#020617', border: '1px solid #1e293b', borderRadius: '12px' }}
                />
                <Area type="monotone" dataKey="fps" stroke="#34d399" strokeWidth={2} fillOpacity={1} fill="url(#colorFps)" name="Streaming FPS" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Historical charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Motion Events Bar Chart */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/40 flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-slate-500" />
            <span className="text-sm font-semibold text-slate-200">Motion Events Histogram</span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={histData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#475569" fontSize={9} />
                <YAxis stroke="#475569" fontSize={9} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#020617', border: '1px solid #1e293b', borderRadius: '12px' }}
                />
                <Bar dataKey="motionEvents" fill="#10b981" radius={[4, 4, 0, 0]} name="Events Count" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Disk write storage growth */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/40 flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-slate-500" />
            <span className="text-sm font-semibold text-slate-200">Sustained Disk Writes (GB)</span>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={histData}>
                <defs>
                  <linearGradient id="colorGb" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#475569" fontSize={9} />
                <YAxis stroke="#475569" fontSize={9} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#020617', border: '1px solid #1e293b', borderRadius: '12px' }}
                />
                <Area type="monotone" dataKey="gbWritten" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorGb)" name="GB Written" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
