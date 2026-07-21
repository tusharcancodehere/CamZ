import React from 'react'
import { useStore } from '../store/useStore'
import { AlertCircle, CheckCircle, Info, X, AlertTriangle } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'

export const NotificationToast: React.FC = () => {
  const { notifications, removeNotification } = useStore()

  const icons = {
    success: <CheckCircle className="h-5 w-5 text-emerald-400" />,
    error: <AlertCircle className="h-5 w-5 text-rose-400" />,
    warning: <AlertTriangle className="h-5 w-5 text-amber-400" />,
    info: <Info className="h-5 w-5 text-blue-400" />,
  }

  const bgColors = {
    success: 'bg-emerald-950/80 border-emerald-900/50',
    error: 'bg-rose-950/80 border-rose-900/50',
    warning: 'bg-amber-950/80 border-amber-900/50',
    info: 'bg-blue-950/80 border-blue-900/50',
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-sm w-full">
      <AnimatePresence>
        {notifications.map((n) => (
          <motion.div
            key={n.id}
            initial={{ opacity: 0, y: 15, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className={`flex items-start gap-3 p-4 rounded-xl border backdrop-blur-md shadow-2xl ${bgColors[n.type]}`}
          >
            <div className="flex-shrink-0 mt-0.5">{icons[n.type]}</div>
            <div className="flex-1 text-sm text-slate-100 font-medium">{n.message}</div>
            <button
              onClick={() => removeNotification(n.id)}
              className="flex-shrink-0 text-slate-400 hover:text-slate-200 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
