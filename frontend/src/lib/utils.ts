import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatMoney(amount: number | string | null | undefined, currency = 'сом') {
  if (amount === null || amount === undefined || amount === '') return '—'
  const n = typeof amount === 'string' ? Number(amount) : amount
  if (!Number.isFinite(n)) return '—'
  return `${n.toLocaleString('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${currency}`
}

export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(sec)}`
}

/**
 * Reference "now" for a station timer. While a session is PAUSED the clock must
 * freeze at the moment the pause started (the server only shifts `expires_at`
 * on resume), otherwise the countdown keeps ticking during the pause.
 */
export function effectiveNow(
  station: { status: string | null; paused_at?: string | null },
  now: number,
): number {
  if (station.status === 'PAUSED' && station.paused_at) {
    const t = new Date(station.paused_at).getTime()
    if (Number.isFinite(t)) return t
  }
  return now
}

export function formatClock(date: Date): string {
  return date.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatDate(date: Date): string {
  return date.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}
