import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'
import type { StationState } from '@/types'

interface Props {
  open: boolean
  station: StationState | null
  onClose: () => void
  onDone: (message: string) => void
}

const QUICK = [
  { label: '+15 мин', minutes: 15 },
  { label: '+30 мин', minutes: 30 },
  { label: '+1 час', minutes: 60 },
]

export function ExtendModal({ open, station, onClose, onDone }: Props) {
  const [custom, setCustom] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const doExtend = async (minutes: number) => {
    if (!station?.session_id) return
    setLoading(true)
    setError(null)
    try {
      await api.extendSession(station.session_id, minutes)
      onDone(`Время продлено на ${minutes} мин`)
      onClose()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`Продлить · ${station?.name ?? ''}`}>
      {!station?.session_id ? null : (
        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-2">
            {QUICK.map((q) => (
              <button
                key={q.minutes}
                onClick={() => doExtend(q.minutes)}
                disabled={loading}
                className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white disabled:opacity-50"
              >
                {q.label}
              </button>
            ))}
          </div>

          <div>
            <span className="mb-1.5 block text-xs font-medium text-white/50">Свой вариант</span>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                value={custom}
                onChange={(e) => setCustom(e.target.value)}
                className="flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white outline-none focus:border-accent/50"
                placeholder="минут"
              />
              <Button
                onClick={() => doExtend(Number(custom))}
                disabled={loading || !Number.isFinite(Number(custom)) || Number(custom) <= 0}
              >
                OK
              </Button>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2.5 text-sm text-danger">
              {error}
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
