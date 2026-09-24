import { motion } from 'framer-motion'
import { Pause, Play, Plus, Square, Timer } from 'lucide-react'
import type { StationState } from '@/types'
import { formatMoney, formatDuration, effectiveNow } from '@/lib/utils'

interface Props {
  station: StationState
  now: number
  currency: string
  onStart: (s: StationState) => void
  onExtend: (s: StationState) => void
  onPause: (s: StationState) => void
  onResume: (s: StationState) => void
  onStop: (s: StationState) => void
}

export function StationRow({ station, now, currency, onStart, onExtend, onPause, onResume, onStop }: Props) {
  const free = station.status === null || !station.session_id
  const isOpen = station.session_type === 'OPEN'
  const paused = station.status === 'PAUSED'

  // Freeze the clock at the pause moment so timers don't run while paused.
  const nowRef = effectiveNow(station, now)

  const remaining =
    !free && station.expires_at
      ? Math.max(0, Math.ceil((new Date(station.expires_at).getTime() - nowRef) / 1000))
      : 0

  const elapsed =
    !free && station.started_at
      ? Math.max(
          0,
          Math.floor((nowRef - new Date(station.started_at).getTime()) / 1000) -
            station.total_paused_seconds,
        )
      : 0

  const expired = !free && station.status === 'EXPIRED'
  const warn = !free && !isOpen && !expired && remaining <= 300 && remaining > 0

  // OPEN sessions accrue live, exact to the kopeck (per second).
  const displayAmount =
    isOpen && station.price_snapshot != null
      ? (Number(station.price_snapshot) / 3600) * elapsed
      : station.amount

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-2xl border bg-card/60 backdrop-blur-xl p-4 transition-colors ${
        expired
          ? 'border-danger/50 bg-danger/5'
          : warn
            ? 'border-warning/40 bg-warning/5'
            : 'border-white/10'
      }`}
    >
      <div className="flex flex-wrap items-center gap-3 sm:gap-4">
        <div className="min-w-[80px] flex-1 sm:min-w-[90px] sm:flex-none">
          <p className="text-sm font-bold text-white">{station.name}</p>
          <p
            className={`text-xs font-medium uppercase tracking-wide ${
              free
                ? 'text-white/30'
                : expired
                  ? 'text-danger'
                  : warn
                    ? 'text-warning'
                    : paused
                      ? 'text-sky-300'
                      : isOpen
                        ? 'text-emerald-400'
                        : 'text-accent'
            }`}
          >
            {free ? 'FREE' : paused ? 'PAUSED' : expired ? 'EXPIRED' : isOpen ? 'OPEN' : 'ACTIVE'}
          </p>
        </div>

        <div className="text-right sm:flex-1 sm:text-center">
          {free ? (
            <span className="font-mono text-lg text-white/30">—</span>
          ) : isOpen ? (
            <span className="font-mono text-lg font-semibold tabular-nums text-emerald-400">
              {formatDuration(elapsed)}
            </span>
          ) : (
            <span
              className={`font-mono text-lg font-semibold tabular-nums ${
                expired ? 'text-danger' : warn ? 'text-warning' : paused ? 'text-sky-300' : 'text-white'
              }`}
            >
              {expired ? '00:00:00' : formatDuration(remaining)}
            </span>
          )}
        </div>

        <div className="w-24 text-right sm:w-28 sm:text-center">
          {free ? (
            <span className="text-sm text-white/30">—</span>
          ) : (
            <span className="text-sm font-semibold tabular-nums text-white/80">
              {displayAmount != null ? formatMoney(displayAmount, currency) : '—'}
            </span>
          )}
        </div>

        {/* actions */}
        <div className="flex w-full items-center justify-end gap-2 sm:w-auto sm:flex-1">
          {free ? (
            <button
              onClick={() => onStart(station)}
              disabled={!station.is_active}
              className="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-accent/90 disabled:opacity-40"
            >
              <Plus className="h-3.5 w-3.5" /> Start
            </button>
          ) : (
            <>
              {!isOpen && (
                <button
                  onClick={() => onExtend(station)}
                  className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2.5 py-2 text-xs font-medium text-white/70 hover:bg-white/10"
                >
                  <Timer className="h-3.5 w-3.5" /> +15/30/60
                </button>
              )}
              {!paused ? (
                <button
                  onClick={() => onPause(station)}
                  className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2.5 py-2 text-xs font-medium text-white/70 hover:bg-white/10"
                >
                  <Pause className="h-3.5 w-3.5" /> Пауза
                </button>
              ) : (
                <button
                  onClick={() => onResume(station)}
                  className="flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-2 text-xs font-medium text-emerald-300 hover:bg-emerald-500/20"
                >
                  <Play className="h-3.5 w-3.5" /> Resume
                </button>
              )}
              <button
                onClick={() => onStop(station)}
                className="flex items-center gap-1 rounded-lg bg-danger/90 px-3 py-2 text-xs font-semibold text-white hover:bg-danger"
              >
                <Square className="h-3.5 w-3.5" /> Стоп
              </button>
            </>
          )}
        </div>
      </div>
    </motion.div>
  )
}
