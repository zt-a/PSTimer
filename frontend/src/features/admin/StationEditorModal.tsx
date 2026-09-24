import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'
import type { Station, StationType } from '@/types'

interface Props {
  open: boolean
  station: Station | null
  onClose: () => void
  onDone: (message: string) => void
}

export function StationEditorModal({ open, station, onClose, onDone }: Props) {
  const [name, setName] = useState('')
  const [number, setNumber] = useState('')
  const [type, setType] = useState<StationType>('PS5')
  const [active, setActive] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setName(station?.name ?? '')
      setNumber(station ? String(station.number) : '')
      setType(station?.type ?? 'PS5')
      setActive(station?.is_active ?? true)
      setError(null)
    }
  }, [open, station])

  const submit = async () => {
    if (!name.trim() || !Number.isFinite(Number(number))) {
      setError('Укажите название и номер')
      return
    }
    setLoading(true)
    setError(null)
    const payload = {
      name: name.trim(),
      number: Number(number),
      type,
      is_active: active,
    }
    try {
      if (station) {
        await api.updateStation(station.id, payload)
        onDone('Станция обновлена')
      } else {
        await api.createStation(payload)
        onDone('Станция создана')
      }
      onClose()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={station ? 'Редактировать станцию' : 'Новая станция'}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-white/50">Название</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white outline-none focus:border-accent/50"
              placeholder="PS #11"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-white/50">Номер</span>
            <input
              type="number"
              min={1}
              value={number}
              onChange={(e) => setNumber(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white outline-none focus:border-accent/50"
            />
          </label>
        </div>

        <div>
          <span className="mb-1.5 block text-xs font-medium text-white/50">Тип</span>
          <div className="grid grid-cols-2 gap-2">
            {(['PS5', 'PS4'] as StationType[]).map((t) => (
              <button
                key={t}
                onClick={() => setType(t)}
                className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                  type === t
                    ? 'border-accent/60 bg-accent/10 text-white'
                    : 'border-white/10 bg-white/5 text-white/60 hover:bg-white/10'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={active}
            onChange={(e) => setActive(e.target.checked)}
            className="h-4 w-4 rounded accent-accent"
          />
          <span className="text-sm text-white/70">Станция активна</span>
        </label>

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2.5 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="flex gap-2 pt-1">
          <Button variant="secondary" className="flex-1" onClick={onClose} disabled={loading}>
            Отмена
          </Button>
          <Button className="flex-1" onClick={submit} disabled={loading}>
            {loading ? '…' : 'Сохранить'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
