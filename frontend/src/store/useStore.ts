import { create } from 'zustand'

export interface Notification {
  id: string
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
}

export interface Settings {
  STREAM_FPS: number
  MOTION_THRESHOLD: number
  MOTION_MIN_AREA: number
  RECORDING_FPS: number
  CAMZ_PREBUFFER_SECONDS: number
  CAMZ_POSTBUFFER_SECONDS: number
  CAMZ_STORAGE_LIMIT_GB: number
  CAMZ_RETENTION_DAYS: number
}

interface AppState {
  activeTab: string
  setActiveTab: (tab: string) => void
  
  mobileSidebarOpen: boolean
  setMobileSidebarOpen: (open: boolean) => void
  
  health: any | null
  fetchHealth: () => Promise<void>
  
  recordings: any[]
  fetchRecordings: () => Promise<void>
  
  storage: any | null
  fetchStorage: () => Promise<void>
  
  settings: Settings | null
  fetchSettings: () => Promise<void>
  updateSettings: (newSettings: Partial<Settings>) => Promise<boolean>
  
  logs: string[]
  fetchLogs: () => Promise<void>
  
  notifications: Notification[]
  addNotification: (message: string, type: Notification['type']) => void
  removeNotification: (id: string) => void
}

export const useStore = create<AppState>((set, get) => ({
  activeTab: 'dashboard',
  setActiveTab: (activeTab) => set({ activeTab }),
  
  mobileSidebarOpen: false,
  setMobileSidebarOpen: (mobileSidebarOpen) => set({ mobileSidebarOpen }),
  
  health: null,
  fetchHealth: async () => {
    try {
      const res = await fetch('/health')
      if (res.ok) {
        const data = await res.json()
        // Only update state when data actually changes to prevent unnecessary rerenders
        const current = get().health
        if (JSON.stringify(current) !== JSON.stringify(data)) {
          set({ health: data })
        }
      }
    } catch (err) {
      console.error('Failed to fetch health metrics:', err)
    }
  },
  
  recordings: [],
  fetchRecordings: async () => {
    try {
      const res = await fetch('/recordings')
      if (res.ok) {
        const data = await res.json()
        set({ recordings: data })
      }
    } catch (err) {
      console.error('Failed to fetch recordings:', err)
    }
  },
  
  storage: null,
  fetchStorage: async () => {
    try {
      const res = await fetch('/storage')
      if (res.ok) {
        const data = await res.json()
        set({ storage: data })
      }
    } catch (err) {
      console.error('Failed to fetch storage stats:', err)
    }
  },
  
  settings: null,
  fetchSettings: async () => {
    try {
      const res = await fetch('/settings')
      if (res.ok) {
        const data = await res.json()
        set({ settings: data })
      }
    } catch (err) {
      console.error('Failed to fetch settings:', err)
    }
  },
  
  updateSettings: async (newSettings) => {
    try {
      const res = await fetch('/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings),
      })
      if (res.ok) {
        const data = await res.json()
        set({ settings: data.settings })
        get().addNotification('Settings updated successfully', 'success')
        return true
      }
    } catch (err) {
      console.error('Failed to update settings:', err)
    }
    get().addNotification('Failed to update settings', 'error')
    return false
  },
  
  logs: [],
  fetchLogs: async () => {
    try {
      const res = await fetch('/logs?limit=100')
      if (res.ok) {
        const data = await res.json()
        set({ logs: data })
      }
    } catch (err) {
      console.error('Failed to fetch logs:', err)
    }
  },
  
  notifications: [],
  addNotification: (message, type) => {
    const id = Math.random().toString(36).substring(2, 9)
    set((state) => ({
      notifications: [...state.notifications, { id, message, type }],
    }))
    setTimeout(() => {
      get().removeNotification(id)
    }, 4000)
  },
  removeNotification: (id) => {
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    }))
  },
}))
