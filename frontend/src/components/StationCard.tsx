import { motion } from 'framer-motion'
import { Activity, Clock, Pause, Play, Square, Timer } from 'lucide-react'
import type { StationState } from '@/types'
import { formatMoney, effectiveNow } from '@/lib/utils'

interface Props {
  station: StationState
  now: number
  currency: string
  onTogglePause?: (s: StationState) => void
  onStop?: (s: StationState) => void
  onStart?: (s: StationState) => void
  interactive?: boolean
}

function deriveDisplay(station: StationState, rawNow: number) {
  // Freeze the clock at the pause moment so timers don't run while paused.
  const now = effectiveNow(station, rawNow)
  const FREE = station.status === null || !station.session_id
  if (FREE) {
    return { label: 'СВОБОДНО', sub: 'Ожидание игрока', color: 'muted' }
  }
  if (station.session_type === 'OPEN') {
    return {
      label: 'OPEN',
      sub: 'Сессия продолжается',
      remaining: null,
      elapsed: elapsedSeconds(station, now),
      color: 'open',
    }
  }
  const remaining = Math.max(0, Math.ceil((new Date(station.expires_at!).getTime() - now) / 1000))
  if (station.status === 'PAUSED') {
    return { label: 'ПАУЗА', sub: 'Приостановлено', remaining, color: 'paused' }
  }
  if (station.status === 'EXPIRED' || remaining === 0) {
    return { label: 'ВРЕМЯ ЗАКОНЧИЛОСЬ', sub: 'Ожидает оператора', remaining: 0, color: 'expired' }
  }
  if (remaining <= 300) {
    return { label: 'ИГРАЕТ', sub: `Осталось ${formatMin(remaining)}`, remaining, color: 'warning' }
  }
  return { label: 'ИГРАЕТ', sub: 'До конца', remaining, color: 'active' }
}

function elapsedSeconds(station: StationState, now: number): number {
  const elapsed = Math.floor((now - new Date(station.started_at!).getTime()) / 1000)
  return Math.max(0, elapsed - station.total_paused_seconds)
}

function formatMin(s: number) {
  const m = Math.ceil(s / 60)
  if (m === 1) return '1 минута'
  if (m < 5) return `${m} минуты`
  return `${m} минут`
}

const colorCls: Record<
  string,
  { ring: string; badge: string; text: string; glow: string; icon: string }
> = {
  muted: {
    ring: 'border-white/5',
    badge: 'bg-white/5 text-white/60',
    text: 'text-white/40',
    glow: '',
    icon: 'text-white/30',
  },
  active: {
    ring: 'border-accent/40',
    badge: 'bg-accent/15 text-accent',
    text: 'text-accent',
    glow: 'shadow-glow',
    icon: 'text-accent',
  },
  warning: {
    ring: 'border-warning/50',
    badge: 'bg-warning/15 text-warning',
    text: 'text-warning',
    glow: 'shadow-glow-warning',
    icon: 'text-warning',
  },
  expired: {
    ring: 'border-danger/60',
    badge: 'bg-danger/20 text-danger',
    text: 'text-danger',
    glow: 'shadow-glow-danger',
    icon: 'text-danger',
  },
  open: {
    ring: 'border-primary/40',
    badge: 'bg-primary/15 text-primary',
    text: 'text-primary',
    glow: 'shadow-glow',
    icon: 'text-primary',
  },
  paused: {
    ring: 'border-sky-400/40',
    badge: 'bg-sky-400/15 text-sky-300',
    text: 'text-sky-300',
    glow: '',
    icon: 'text-sky-300',
  },
}

export function StationCard({ station, now, currency, interactive = false, onTogglePause, onStop, onStart }: Props) {
  const d = deriveDisplay(station, now)
  const c = colorCls[d.color]
  const isWarning = d.color === 'warning'
  const isExpired = d.color === 'expired'
  const isOpen = station.session_type === 'OPEN'
  const isPaused = d.color === 'paused'

  const amount = station.amount ?? 0
  const elapsed = (d as any).elapsed

  // OPEN sessions accrue live, exact to the kopeck (per second).
  const liveAmount =
    isOpen && station.price_snapshot != null && elapsed != null
      ? (Number(station.price_snapshot) / 3600) * elapsed
      : amount

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: 'spring', stiffness: 120, damping: 18 }}
      className={`relative overflow-hidden rounded-2xl border bg-card/60 backdrop-blur-xl p-6 flex flex-col justify-between transition-colors duration-500 min-h-[220px] ${
        c.ring
      } ${c.glow} ${isWarning ? 'animate-pulse-soft' : ''}`}
      data-status={d.color}
    >
      {/* subtle radial glow in a corner */}
      <div
        className={`pointer-events-none absolute -top-24 -right-24 h-56 w-56 rounded-full blur-3xl ${
          d.color === 'expired'
            ? 'bg-danger/20'
            : d.color === 'warning'
              ? 'bg-warning/20'
              : d.color === 'active'
                ? 'bg-accent/15'
                : d.color === 'open'
                  ? 'bg-primary/15'
                  : 'bg-transparent'
        }`}
      />

      {/* header row */}
      <div className="relative flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/5 border border-white/10 text-sm font-bold text-white/80">
            {station.name.replace(/\D/g, '')}
          </span>
          <span className="text-lg font-semibold tracking-tight text-white/90">
            {station.name}
          </span>
        </div>
        {station.status !== null && station.session_id ? (
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wider ${c.badge}`}
          >
            {isPaused ? (
              <Pause className="h-3 w-3" />
            ) : isExpired ? (
              <Clock className="h-3 w-3" />
            ) : isOpen ? (
              <Activity className="h-3 w-3" />
            ) : isWarning ? (
              <Timer className="h-3 w-3" />
            ) : (
              <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
            )}
            {d.label}
          </span>
        ) : (
          <span className="inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-white/30 bg-white/5">
            FREE
          </span>
        )}
      </div>

      {/* time + money */}
      <div className="relative mt-2 flex flex-col items-center justify-center flex-1">
        {d.color === 'muted' ? (
          <div className="text-center">
            <p className="text-2xl font-bold uppercase tracking-widest text-white/30">
              Свободно
            </p>
            <p className="mt-1 text-sm text-white/25">{d.sub}</p>
          </div>
        ) : isOpen ? (
          <div className="text-center">
            <p className="font-mono text-4xl font-semibold tabular-nums tracking-tight text-white">
              {fmt(elapsed)}
            </p>
            <div className="mt-2 flex items-center justify-center gap-3">
              <span className="text-lg font-medium text-primary/90 tabular-nums">
                {formatMoney(liveAmount, currency)}
              </span>
            </div>
            <p className="mt-1 text-xs text-white/30">{d.sub}</p>
          </div>
        ) : (
          <div className="text-center">
            <p
              className={`font-mono text-4xl font-semibold tabular-nums tracking-tight ${
                isWarning
                  ? 'text-warning'
                  : isExpired
                    ? 'text-danger'
                    : isPaused
                      ? 'text-sky-300'
                      : 'text-white'
              }`}
            >
              {isExpired ? '00:00:00' : fmt(d.remaining!)}
            </p>
            <div className="mt-2 flex items-center justify-center gap-3 text-lg font-medium tabular-nums">
              <span className={c.text}>{formatMoney(amount, currency)}</span>
            </div>
            <p
              className={`mt-1 text-xs font-medium uppercase tracking-wider ${
                isExpired ? 'text-danger/80' : 'text-white/30'
              }`}
            >
              {d.sub}
            </p>
          </div>
        )}
      </div>

      {/* interactive admin actions */}
      {interactive && station.session_id && (
        <div className="relative mt-4 flex items-center gap-2">
          {!isOpen && (
            <button
              onClick={() => onTogglePause?.(station)}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 py-2 text-xs font-medium text-white/80 transition-colors"
            >
              {isPaused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
              {isPaused ? 'Продолжить' : 'Пауза'}
            </button>
          )}
          <button
            onClick={() => onStop?.(station)}
            className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-danger/20 hover:bg-danger/30 border border-danger/30 py-2 text-xs font-semibold text-danger transition-colors"
          >
            <Square className="h-3.5 w-3.5" />
            Стоп
          </button>
        </div>
      )}
      {interactive && !station.session_id && (
        <button
          onClick={() => onStart?.(station)}
          disabled={!station.is_active}
          className="relative mt-4 w-full rounded-lg bg-accent/90 hover:bg-accent border border-accent/40 py-2.5 text-sm font-semibold text-white transition-colors disabled:opacity-40"
        >
          Start
        </button>
      )}
    </motion.div>
  )
}

function fmt(seconds: number) {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}
