import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'
import { formatDuration } from '@/lib/utils'
import type { DashboardResponse, StationState } from '@/types'

interface Props {
  open: boolean
  station: StationState | null
  dashboard: DashboardResponse | null
  onClose: () => void
  onDone: (message: string) => void
}

export function StopModal({ open, station, dashboard, onClose, onDone }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!open) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [open])

  if (!station?.session_id) return null

  const elapsedSeconds =
    station.started_at && now
      ? Math.max(
          0,
          Math.floor((new Date(station.started_at).getTime() - now) / 1000) * -1 -
            station.total_paused_seconds,
        )
      : 0

  const stop = async () => {
    setLoading(true)
    setError(null)
    try {
      await api.stopSession(station.session_id!)
      onDone(`Сессия закрыта · ${station.name}`)
      onClose()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`Завершить сессию · ${station.name}`}>
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
            <p className="text-xs text-white/40">Длительность</p>
            <p className="mt-1 font-mono text-xl font-semibold tabular-nums text-white">
              {formatDuration(elapsedSeconds)}
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-center">
            <p className="text-xs text-white/40">Тариф</p>
            <p className="mt-1 text-xl font-semibold text-white tabular-nums">
              {station.price_snapshot != null
                ? `${station.price_snapshot} ${dashboard?.currency ?? 'сом'}/час`
                : '—'}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
          <span className="text-sm text-white/60">К оплате</span>
          <span className="text-2xl font-bold text-emerald-400 tabular-nums">
            {station.amount != null
              ? `${station.amount} ${dashboard?.currency ?? 'сом'}`
              : '—'}
          </span>
        </div>

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2.5 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <Button variant="secondary" className="flex-1" onClick={onClose} disabled={loading}>
            Отмена
          </Button>
          <Button variant="danger" className="flex-1" onClick={stop} disabled={loading}>
            {loading ? '…' : 'Стоп и завершить'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
