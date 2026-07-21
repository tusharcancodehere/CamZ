import React from 'react'
import { useStore } from '../store/useStore'
import {
  Cpu,
  Database,
  HardDrive,
  CheckCircle2,
  AlertTriangle,
  XCircle,
} from 'lucide-react'

export const Health: React.FC = () => {
  const { health } = useStore()

  const systemStatus = health?.status || 'degraded'
  const cameraState = health?.camera?.status || 'disconnected'
  const cpuVal = health?.system?.cpu_percent || 0
  const memPct = health?.system?.memory_percent || 0
  const freeDisk = health?.recording?.storage_free_bytes || 0
  const usedDisk = health?.recording?.storage_used_bytes || 0
  const limitDisk = health?.recording?.storage_limit_bytes || 0
  const queueSize = health?.recording?.queue_size || 0

  const statusIcons = {
    ok: <CheckCircle2 className="h-6 w-6 text-emerald-400" />,
    degraded: <AlertTriangle className="h-6 w-6 text-amber-400 animate-pulse" />,
    critical: <XCircle className="h-6 w-6 text-rose-500 animate-pulse" />,
  }

  const formatSize = (bytes: number) => {
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
  }

  const diagnostics = [
    {
      name: 'Camera Connection',
      status: cameraState === 'active' ? 'ok' : 'critical',
      message: cameraState === 'active' ? 'Physical camera link is active and streaming.' : 'Camera hardware disconnected or read failure.',
      icon: <CheckCircle2 className="h-4 w-4" />,
    },
    {
      name: 'Streaming Pipeline',
      status: health?.pipeline?.streaming_fps > 0 ? 'ok' : 'degraded',
      message: `Streaming thread running at ${health?.pipeline?.streaming_fps?.toFixed(1) || 0} FPS.`,
      icon: <CheckCircle2 className="h-4 w-4" />,
    },
    {
      name: 'Asynchronous Recorder Queue',
      status: queueSize < 50 ? 'ok' : queueSize < 200 ? 'degraded' : 'critical',
      message: `Recording frame queue is at ${queueSize}/256 frames.`,
      icon: <CheckCircle2 className="h-4 w-4" />,
    },
    {
      name: 'Storage Disk Limit',
      status: freeDisk > 1024 * 1024 * 1024 ? 'ok' : 'degraded',
      message: limitDisk > 0
        ? `Remaining disk space: ${formatSize(freeDisk)} (Quota: ${formatSize(limitDisk)}).`
        : `Remaining disk space: ${formatSize(freeDisk)}.`,
      icon: <CheckCircle2 className="h-4 w-4" />,
    },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-100">System Diagnostics</h1>
          <p className="text-sm text-slate-500">Subsystem status check list and host operating parameters.</p>
        </div>
      </div>

      {/* Hero Overview */}
      <div className="flex items-center gap-4 p-5 rounded-2xl border border-slate-900 bg-slate-950/40">
        <div className="flex-shrink-0">
          {statusIcons[systemStatus === 'ok' ? 'ok' : 'degraded']}
        </div>
        <div>
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
            System Status: {systemStatus === 'ok' ? 'HEALTHY' : 'DEGRADED'}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            {systemStatus === 'ok'
              ? 'All surveillance systems and background encoders are operating within normal parameters.'
              : 'Some subsystems are offline or running with high latency. Inspect diagnostics list.'}
          </p>
        </div>
      </div>

      {/* Diagnostics List */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-900 pb-2">
            Subsystem Status Checks
          </h3>

          {diagnostics.map((diag, index) => (
            <div
              key={index}
              className="p-4 rounded-xl border border-slate-900 bg-slate-950/20 flex items-start justify-between gap-4"
            >
              <div className="flex-1 space-y-1">
                <span className="text-xs font-semibold text-slate-200 block">{diag.name}</span>
                <span className="text-[10px] text-slate-500 block">{diag.message}</span>
              </div>
              <div className="flex-shrink-0 mt-0.5">
                {diag.status === 'ok' ? (
                  <span className="text-emerald-400 font-bold uppercase text-[9px] bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                    OK
                  </span>
                ) : diag.status === 'degraded' ? (
                  <span className="text-amber-400 font-bold uppercase text-[9px] bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                    WARN
                  </span>
                ) : (
                  <span className="text-rose-500 font-bold uppercase text-[9px] bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded-full">
                    FAIL
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Resources Summary */}
        <div className="space-y-4">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-900 pb-2">
            Resource Consumption Stats
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* CPU */}
            <div className="p-4 rounded-xl border border-slate-900 bg-slate-950/20 flex flex-col gap-3">
              <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
                <span>CPU Load</span>
                <Cpu className="h-4 w-4" />
              </div>
              <div>
                <span className="text-2xl font-extrabold text-slate-200 font-mono">{cpuVal}%</span>
              </div>
            </div>

            {/* RAM */}
            <div className="p-4 rounded-xl border border-slate-900 bg-slate-950/20 flex flex-col gap-3">
              <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
                <span>Memory usage</span>
                <Database className="h-4 w-4" />
              </div>
              <div>
                <span className="text-2xl font-extrabold text-slate-200 font-mono">{memPct.toFixed(1)}%</span>
              </div>
            </div>

            {/* Storage usage */}
            <div className="p-4 rounded-xl border border-slate-900 bg-slate-950/20 flex flex-col gap-3 col-span-1 sm:col-span-2">
              <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
                <span>Storage Limit (Quota used)</span>
                <HardDrive className="h-4 w-4" />
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span>Used: {formatSize(usedDisk)}</span>
                  <span>Free: {formatSize(freeDisk)}</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-slate-900 overflow-hidden">
                  <div
                    className="h-full bg-emerald-400 rounded-full transition-all duration-300"
                    style={{ width: `${(usedDisk / (usedDisk + freeDisk || 1)) * 100}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
