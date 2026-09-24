import { useEffect, useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'
import type { Tariff } from '@/types'

interface Props {
  open: boolean
  tariff: Tariff | null
  onClose: () => void
  onDone: (message: string) => void
}

export function TariffEditorModal({ open, tariff, onClose, onDone }: Props) {
  const [name, setName] = useState('')
  const [price, setPrice] = useState('')
  const [active, setActive] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setName(tariff?.name ?? '')
      setPrice(tariff ? String(tariff.price_per_hour) : '')
      setActive(tariff?.is_active ?? true)
      setError(null)
    }
  }, [open, tariff])

  const submit = async () => {
    if (!name.trim() || !Number.isFinite(Number(price)) || Number(price) <= 0) {
      setError('Укажите название и цену больше 0')
      return
    }
    setLoading(true)
    setError(null)
    const payload = {
      name: name.trim(),
      price_per_hour: Number(price),
      is_active: active,
    }
    try {
      if (tariff) {
        await api.updateTariff(tariff.id, payload)
        onDone('Тариф обновлён')
      } else {
        await api.createTariff(payload)
        onDone('Тариф создан')
      }
      onClose()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={tariff ? 'Редактировать тариф' : 'Новый тариф'}>
      <div className="space-y-4">
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-white/50">Название</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white outline-none focus:border-accent/50"
            placeholder="PS5 Standard"
          />
        </label>

        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-white/50">Цена за час</span>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={1}
              step="0.5"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className="flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white outline-none focus:border-accent/50"
              placeholder="300"
            />
            <span className="text-sm text-white/40">сом</span>
          </div>
        </label>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={active}
            onChange={(e) => setActive(e.target.checked)}
            className="h-4 w-4 rounded accent-accent"
          />
          <span className="text-sm text-white/70">Тариф активен</span>
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
            {loading ? '…' : tariff ? 'Сохранить' : 'Создать'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
