import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Play, Timer } from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'
import { formatMoney } from '@/lib/utils'
import type { StationState, Tariff } from '@/types'

interface Props {
  open: boolean
  station: StationState | null
  tariffs: Tariff[]
  currency: string
  onClose: () => void
  onDone: (message: string) => void
}

const PRESETS = [
  { label: '30 мин', minutes: 30 },
  { label: '1 час', minutes: 60 },
  { label: '1.5 часа', minutes: 90 },
  { label: '2 часа', minutes: 120 },
]

export function StartSessionModal({ open, station, tariffs, currency, onClose, onDone }: Props) {
  const [tariffId, setTariffId] = useState<number | ''>('')
  const [mode, setMode] = useState<'fixed' | 'open'>('fixed')
  const [preset, setPreset] = useState<number>(60)
  const [custom, setCustom] = useState<string>('')
  const [customActive, setCustomActive] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeTariffs = useMemo(() => tariffs.filter((t) => t.is_active), [tariffs])
  const tariff = tariffs.find((t) => t.id === tariffId)

  useEffect(() => {
    if (open) {
      setTariffId(activeTariffs[0]?.id ?? '')
      setMode('fixed')
      setCustomActive(false)
      setError(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const durationMinutes = customActive ? Number(custom) : preset

  const price =
    mode === 'open' || !tariff || !Number.isFinite(durationMinutes)
      ? null
      : tariff.price_per_hour * (durationMinutes / 60)

  const submit = async () => {
    if (!station || !tariff) return
    setLoading(true)
    setError(null)
    try {
      await api.startSession({
        station_id: station.id,
        tariff_id: tariff.id,
        is_open: mode === 'open',
        duration_minutes: mode === 'fixed' ? durationMinutes : undefined,
      })
      onDone(mode === 'open' ? 'Открытая сессия запущена' : `Сессия ${durationMinutes} мин запущена`)
      onClose()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`Новая сессия · ${station?.name ?? ''}`}>
      {!station ? null : (
        <div className="space-y-5">
          <div>
            <span className="mb-1.5 block text-xs font-medium text-white/50">Тариф</span>
            <div className="grid grid-cols-2 gap-2">
              {activeTariffs.length === 0 && (
                <p className="col-span-2 text-sm text-white/40">Сначала создайте тариф</p>
              )}
              {activeTariffs.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTariffId(t.id)}
                  className={`rounded-xl border px-3 py-2.5 text-left transition-colors ${
                    tariffId === t.id
                      ? 'border-accent/60 bg-accent/10'
                      : 'border-white/10 bg-white/5 hover:bg-white/10'
                  }`}
                >
                  <span className="block text-sm font-semibold text-white">{t.name}</span>
                  <span className="block text-xs text-white/40">
                    {formatMoney(t.price_per_hour, `${currency}/час`)}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <span className="mb-1.5 block text-xs font-medium text-white/50">Режим</span>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setMode('fixed')}
                className={`flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-medium transition-colors ${
                  mode === 'fixed'
                    ? 'border-accent/60 bg-accent/10 text-white'
                    : 'border-white/10 bg-white/5 text-white/50 hover:bg-white/10'
                }`}
              >
                <Timer className="h-4 w-4" /> По времени
              </button>
              <button
                onClick={() => setMode('open')}
                className={`flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-sm font-medium transition-colors ${
                  mode === 'open'
                    ? 'border-emerald-500/60 bg-emerald-500/10 text-white'
                    : 'border-white/10 bg-white/5 text-white/50 hover:bg-white/10'
                }`}
              >
                <Play className="h-4 w-4" /> Открытая
              </button>
            </div>
          </div>

          {mode === 'fixed' && (
            <div>
              <span className="mb-1.5 block text-xs font-medium text-white/50">Длительность</span>
              <div className="grid grid-cols-4 gap-2">
                {PRESETS.map((p) => (
                  <button
                    key={p.minutes}
                    onClick={() => {
                      setPreset(p.minutes)
                      setCustomActive(false)
                    }}
                    className={`rounded-xl border px-2 py-2.5 text-xs font-medium transition-colors ${
                      !customActive && preset === p.minutes
                        ? 'border-accent/60 bg-accent/10 text-white'
                        : 'border-white/10 bg-white/5 text-white/60 hover:bg-white/10'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <div className="mt-2 flex items-center gap-2">
                <button
                  onClick={() => {
                    setCustomActive(!customActive)
                    if (!customActive) setCustom('45')
                  }}
                  className={`rounded-xl border px-3 py-2 text-xs font-medium transition-colors ${
                    customActive
                      ? 'border-accent/60 bg-accent/10 text-white'
                      : 'border-white/10 bg-white/5 text-white/60 hover:bg-white/10'
                  }`}
                >
                  Свой
                </button>
                {customActive && (
                  <input
                    type="number"
                    min={1}
                    value={custom}
                    onChange={(e) => setCustom(e.target.value)}
                    className="w-24 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent/50"
                    placeholder="мин"
                  />
                )}
              </div>
            </div>
          )}

          {mode === 'open' && tariff && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3"
            >
              <p className="text-sm text-white/60">
                Открытая сессия · {formatMoney(tariff.price_per_hour, `${currency}/час`)}
              </p>
              <p className="mt-1 text-xs text-white/40">
                Оплата по факту времени, точный расчёт до копейки (посекундно)
              </p>
            </motion.div>
          )}

          {mode === 'fixed' && tariff && (
            <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 p-3">
              <span className="text-sm text-white/60">Стоимость</span>
              <span className="text-lg font-bold text-white tabular-nums">
                {price != null && Number.isFinite(price)
                  ? formatMoney(Number(price.toFixed(2)), currency)
                  : '—'}
              </span>
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-2.5 text-sm text-danger">
              {error}
            </div>
          )}

          <div className="flex gap-2 pt-1">
            <Button variant="secondary" className="flex-1" onClick={onClose} disabled={loading}>
              Отмена
            </Button>
            <Button
              className="flex-1"
              onClick={submit}
              disabled={
                loading ||
                activeTariffs.length === 0 ||
                (mode === 'fixed' && (!Number.isFinite(durationMinutes) || durationMinutes <= 0))
              }
            >
              {loading ? '…' : mode === 'open' ? 'Запустить OPEN' : 'Начать сессию'}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  )
}
