import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, XCircle } from 'lucide-react'

export interface ToastData {
  id: number
  message: string
  type: 'success' | 'error'
}

export function ToastViewport({ toasts }: { toasts: ToastData[] }) {
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 40, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 40, scale: 0.9 }}
            className={`pointer-events-auto flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-medium shadow-lg backdrop-blur-xl ${
              t.type === 'success'
                ? 'border-emerald-500/30 bg-emerald-500/15 text-emerald-300'
                : 'border-danger/30 bg-danger/15 text-red-300'
            }`}
          >
            {t.type === 'success' ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <XCircle className="h-4 w-4" />
            )}
            {t.message}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
