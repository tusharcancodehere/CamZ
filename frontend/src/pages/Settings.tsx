import React, { useState, useEffect } from 'react'
import { useStore } from '../store/useStore'
import type { Settings as SettingsType } from '../store/useStore'
import { Save, RotateCcw } from 'lucide-react'

export const Settings: React.FC = () => {
  const { settings, fetchSettings, updateSettings } = useStore()
  const [form, setForm] = useState<SettingsType | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchSettings()
  }, [])

  useEffect(() => {
    if (settings) {
      setForm(settings)
    }
  }, [settings])

  if (!form) {
    return (
      <div className="py-24 text-center text-xs text-slate-500 animate-pulse">
        Loading configuration parameters...
      </div>
    )
  }

  const validateField = (name: string, val: any): string => {
    const num = Number(val)
    if (isNaN(num)) return 'Value must be a number'
    
    if (name === 'STREAM_FPS') {
      if (num < 5 || num > 60) return 'Stream FPS must be between 5 and 60'
    } else if (name === 'RECORDING_FPS') {
      if (num < 5 || num > 60) return 'Recording FPS must be between 5 and 60'
    } else if (name === 'MOTION_THRESHOLD') {
      if (num < 5 || num > 100) return 'Motion threshold must be between 5 and 100'
    } else if (name === 'MOTION_MIN_AREA') {
      if (num < 100 || num > 50000) return 'Min Area must be between 100 and 50000 px'
    } else if (name === 'CAMZ_PREBUFFER_SECONDS') {
      if (num < 1 || num > 30) return 'Pre-buffer must be between 1 and 30 seconds'
    } else if (name === 'CAMZ_POSTBUFFER_SECONDS') {
      if (num < 1 || num > 60) return 'Post-buffer must be between 1 and 60 seconds'
    } else if (name === 'CAMZ_STORAGE_LIMIT_GB') {
      if (num <= 0.1 || num > 2000) return 'Storage limit must be between 0.1 and 2000 GB'
    } else if (name === 'CAMZ_RETENTION_DAYS') {
      if (num < 1 || num > 365) return 'Retention must be between 1 and 365 days'
    }
    return ''
  }

  const handleChange = (name: keyof SettingsType, value: string) => {
    const error = validateField(name, value)
    setErrors((prev) => ({ ...prev, [name]: error }))
    
    // Parse numeric fields safely
    const numVal = value === '' ? '' : Number(value)
    setForm((prev) => (prev ? { ...prev, [name]: numVal } : null))
  }

  const handleReset = () => {
    if (settings) {
      setForm(settings)
      setErrors({})
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate all fields
    const newErrors: Record<string, string> = {}
    let hasErrors = false
    
    Object.entries(form).forEach(([k, v]) => {
      const err = validateField(k, v)
      if (err) {
        newErrors[k] = err
        hasErrors = true
      }
    })
    
    if (hasErrors) {
      setErrors(newErrors)
      return
    }

    setSaving(true)
    await updateSettings(form)
    setSaving(false)
  }

  const hasChanges = JSON.stringify(settings) !== JSON.stringify(form)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-900 pb-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-100">System Settings</h1>
          <p className="text-sm text-slate-500">Edit surveillance thresholds, streaming pacing, and storage retention.</p>
        </div>

        {hasChanges && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-900 border border-slate-800 hover:bg-slate-850 text-slate-300 transition-colors"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Undo changes
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-emerald-500 hover:bg-emerald-600 text-slate-950 transition-colors shadow-lg shadow-emerald-500/10"
            >
              <Save className="h-3.5 w-3.5" />
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-4xl w-full">
        {/* Stream Settings */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/40 flex flex-col gap-4">
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider border-b border-slate-900/50 pb-2">
            Stream Configuration
          </h3>

          <div className="space-y-3">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-500 font-semibold uppercase">Stream Frame Rate (FPS)</label>
              <input
                type="number"
                value={form.STREAM_FPS}
                onChange={(e) => handleChange('STREAM_FPS', e.target.value)}
                className={`h-9 rounded-xl bg-slate-900/40 border px-3 text-xs text-slate-200 focus:outline-none ${
                  errors.STREAM_FPS ? 'border-rose-900 focus:border-rose-800' : 'border-slate-900 focus:border-slate-800'
                }`}
              />
              {errors.STREAM_FPS && <span className="text-[10px] text-rose-500 mt-0.5">{errors.STREAM_FPS}</span>}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-500 font-semibold uppercase">Recording Target FPS</label>
              <input
                type="number"
                value={form.RECORDING_FPS}
                onChange={(e) => handleChange('RECORDING_FPS', e.target.value)}
                className={`h-9 rounded-xl bg-slate-900/40 border px-3 text-xs text-slate-200 focus:outline-none ${
                  errors.RECORDING_FPS ? 'border-rose-900 focus:border-rose-800' : 'border-slate-900 focus:border-slate-800'
                }`}
              />
              {errors.RECORDING_FPS && <span className="text-[10px] text-rose-500 mt-0.5">{errors.RECORDING_FPS}</span>}
            </div>
          </div>
        </div>

        {/* Motion & Video Buffers */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/40 flex flex-col gap-4">
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider border-b border-slate-900/50 pb-2">
            Motion Detection & Buffers
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-500 font-semibold uppercase">Motion Threshold</label>
              <input
                type="number"
                value={form.MOTION_THRESHOLD}
                onChange={(e) => handleChange('MOTION_THRESHOLD', e.target.value)}
                className={`h-9 rounded-xl bg-slate-900/40 border px-3 text-xs text-slate-200 focus:outline-none ${
                  errors.MOTION_THRESHOLD ? 'border-rose-900 focus:border-rose-800' : 'border-slate-900 focus:border-slate-800'
                }`}
              />
              {errors.MOTION_THRESHOLD && <span className="text-[10px] text-rose-500 mt-0.5">{errors.MOTION_THRESHOLD}</span>}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-500 font-semibold uppercase">Min Area (Pixels)</label>
              <input
                type="number"
                value={form.MOTION_MIN_AREA}
                onChange={(e) => handleChange('MOTION_MIN_AREA', e.target.value)}
                className={`h-9 rounded-xl bg-slate-900/40 border px-3 text-xs text-slate-200 focus:outline-none ${
                  errors.MOTION_MIN_AREA ? 'border-rose-900 focus:border-rose-800' : 'border-slate-900 focus:border-slate-800'
                }`}
              />
              {errors.MOTION_MIN_AREA && <span className="text-[10px] text-rose-500 mt-0.5">{errors.MOTION_MIN_AREA}</span>}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-500 font-semibold uppercase">Prebuffer Seconds</label>
              <input
                type="number"
                value={form.CAMZ_PREBUFFER_SECONDS}
                onChange={(e) => handleChange('CAMZ_PREBUFFER_SECONDS', e.target.value)}
                className={`h-9 rounded-xl bg-slate-900/40 border px-3 text-xs text-slate-200 focus:outline-none ${
                  errors.CAMZ_PREBUFFER_SECONDS ? 'border-rose-900 focus:border-rose-800' : 'border-slate-900 focus:border-slate-800'
                }`}
              />
              {errors.CAMZ_PREBUFFER_SECONDS && <span className="text-[10px] text-rose-500 mt-0.5">{errors.CAMZ_PREBUFFER_SECONDS}</span>}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-500 font-semibold uppercase">Postbuffer Seconds</label>
              <input
                type="number"
                value={form.CAMZ_POSTBUFFER_SECONDS}
                onChange={(e) => handleChange('CAMZ_POSTBUFFER_SECONDS', e.target.value)}
                className={`h-9 rounded-xl bg-slate-900/40 border px-3 text-xs text-slate-200 focus:outline-none ${
                  errors.CAMZ_POSTBUFFER_SECONDS ? 'border-rose-900 focus:border-rose-800' : 'border-slate-900 focus:border-slate-800'
                }`}
              />
              {errors.CAMZ_POSTBUFFER_SECONDS && <span className="text-[10px] text-rose-500 mt-0.5">{errors.CAMZ_POSTBUFFER_SECONDS}</span>}
            </div>
          </div>
        </div>

        {/* Storage limits */}
        <div className="p-5 rounded-2xl border border-slate-900 bg-slate-950/40 flex flex-col gap-4 col-span-1 lg:col-span-2">
          <h3 className="text-xs font-semibold text-slate-200 uppercase tracking-wider border-b border-slate-900/50 pb-2">
            Storage limits & Quotas
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-500 font-semibold uppercase">Storage Quota Limit (GB)</label>
              <input
                type="number"
                step="0.1"
                value={form.CAMZ_STORAGE_LIMIT_GB}
                onChange={(e) => handleChange('CAMZ_STORAGE_LIMIT_GB', e.target.value)}
                className={`h-9 rounded-xl bg-slate-900/40 border px-3 text-xs text-slate-200 focus:outline-none ${
                  errors.CAMZ_STORAGE_LIMIT_GB ? 'border-rose-900 focus:border-rose-800' : 'border-slate-900 focus:border-slate-800'
                }`}
              />
              {errors.CAMZ_STORAGE_LIMIT_GB && <span className="text-[10px] text-rose-500 mt-0.5">{errors.CAMZ_STORAGE_LIMIT_GB}</span>}
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-500 font-semibold uppercase">Retention Days</label>
              <input
                type="number"
                value={form.CAMZ_RETENTION_DAYS}
                onChange={(e) => handleChange('CAMZ_RETENTION_DAYS', e.target.value)}
                className={`h-9 rounded-xl bg-slate-900/40 border px-3 text-xs text-slate-200 focus:outline-none ${
                  errors.CAMZ_RETENTION_DAYS ? 'border-rose-900 focus:border-rose-800' : 'border-slate-900 focus:border-slate-800'
                }`}
              />
              {errors.CAMZ_RETENTION_DAYS && <span className="text-[10px] text-rose-500 mt-0.5">{errors.CAMZ_RETENTION_DAYS}</span>}
            </div>
          </div>
        </div>
      </form>
    </div>
  )
}
