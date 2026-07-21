import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store/useStore'
import {
  LayoutDashboard,
  Video,
  PlaySquare,
  Camera,
  BarChart3,
  HeartPulse,
  Settings,
  Terminal,
  ChevronLeft,
  ChevronRight,
  Shield,
  X,
} from 'lucide-react'

export const Sidebar: React.FC = () => {
  const { activeTab, mobileSidebarOpen, setMobileSidebarOpen } = useStore()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)

  const menuItems = [
    { id: 'dashboard', name: 'Dashboard', icon: <LayoutDashboard className="h-5 w-5" /> },
    { id: 'live', name: 'Live Camera', icon: <Video className="h-5 w-5" /> },
    { id: 'recordings', name: 'Recordings', icon: <PlaySquare className="h-5 w-5" /> },
    { id: 'snapshots', name: 'Snapshots', icon: <Camera className="h-5 w-5" /> },
    { id: 'analytics', name: 'Analytics', icon: <BarChart3 className="h-5 w-5" /> },
    { id: 'health', name: 'Health', icon: <HeartPulse className="h-5 w-5" /> },
    { id: 'settings', name: 'Settings', icon: <Settings className="h-5 w-5" /> },
    { id: 'logs', name: 'System Logs', icon: <Terminal className="h-5 w-5" /> },
  ]

  return (
    <>
      {/* Mobile Sidebar Backdrop overlay */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-sm md:hidden"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r border-slate-900 bg-slate-950 text-slate-400 transition-all duration-300 md:static ${
          mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        } ${collapsed ? 'w-20' : 'w-64'}`}
      >
        {/* Brand Header */}
        <div className="flex h-16 items-center justify-between px-6 border-b border-slate-900">
          <div className="flex items-center gap-3 font-semibold text-slate-100">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-500">
              <Shield className="h-5 w-5" />
            </div>
            {!collapsed && (
              <span className="bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent font-bold tracking-wider">
                CAMZ
              </span>
            )}
          </div>
          
          {/* Close mobile sidebar button */}
          <button
            onClick={() => setMobileSidebarOpen(false)}
            className="p-1 rounded-lg hover:bg-slate-900 text-slate-500 hover:text-slate-200 md:hidden"
          >
            <X className="h-5 w-5" />
          </button>

          {/* Toggle Collapse Button (hidden on mobile) */}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="absolute -right-3 top-5 z-10 hidden md:flex h-6 w-6 items-center justify-center rounded-full border border-slate-900 bg-slate-950 text-slate-500 hover:text-slate-200 transition-colors shadow-lg"
          >
            {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
          </button>
        </div>

        {/* Nav Menu */}
        <nav className="flex-1 space-y-1.5 p-4">
          {menuItems.map((item) => {
            const active = activeTab === item.id
            return (
              <button
                key={item.id}
                onClick={() => {
                  navigate(item.id === 'dashboard' ? '/' : `/${item.id}`)
                  setMobileSidebarOpen(false)
                }}
                className={`flex w-full items-center gap-4 rounded-xl px-4 py-3 text-sm font-medium transition-all ${
                  active
                    ? 'bg-slate-900 text-emerald-400 border border-slate-800 shadow-inner'
                    : 'hover:bg-slate-900/50 hover:text-slate-200 border border-transparent'
                }`}
              >
                <div className={active ? 'text-emerald-400' : 'text-slate-500'}>
                  {item.icon}
                </div>
                <span className={`md:inline ${collapsed ? 'md:hidden' : ''}`}>{item.name}</span>
              </button>
            )
          })}
        </nav>

        {/* Bottom Footer Details */}
        <div className={`p-6 border-t border-slate-900 text-xs text-slate-600 flex items-center justify-between md:flex ${collapsed ? 'md:hidden' : ''}`}>
          <span>v1.0.0-beta.2</span>
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-slate-500 font-medium">Engine OK</span>
          </div>
        </div>
      </aside>
    </>
  )
}
