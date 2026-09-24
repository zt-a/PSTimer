import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import { useEffect } from 'react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  wide?: boolean
}

export function Modal({ open, onClose, title, children, wide }: ModalProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-3 backdrop-blur-sm sm:p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.94, opacity: 0, y: 16 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.96, opacity: 0, y: 8 }}
            transition={{ type: 'spring', stiffness: 260, damping: 24 }}
            onClick={(e) => e.stopPropagation()}
            className={`relative max-h-[calc(100vh-1.5rem)] w-full overflow-y-auto ${wide ? 'max-w-2xl' : 'max-w-md'} rounded-2xl border border-white/10 bg-card/95 p-5 backdrop-blur-2xl sm:max-h-[calc(100vh-2rem)] sm:p-6`}
          >
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">{title}</h2>
              <button
                onClick={onClose}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-white/50 hover:bg-white/10 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
