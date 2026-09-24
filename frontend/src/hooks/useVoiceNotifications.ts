import { useCallback, useEffect, useRef } from 'react'
import { api } from '@/lib/api'
import { speak } from '@/lib/voice'
import type { DashboardResponse, StationState } from '@/types'

/** Minimal settings subset needed for gating. */
export interface VoiceSettings {
  voice_enabled: boolean
  warning_5_enabled: boolean
  warning_3_enabled: boolean
  warning_1_enabled: boolean
  expired_enabled: boolean
}

function russianSpeech(station: StationState, kind: '5' | '3' | '1' | 'expired'): string {
  const label = `номер ${station.number}`
  switch (kind) {
    case '5':
      return `Внимание. Игровое место ${label}. До окончания игры осталось пять минут.`
    case '3':
      return `Игровое место ${label}. До окончания игры осталось три минуты.`
    case '1':
      return `Игровое место ${label}. До окончания игры осталась одна минута.`
    case 'expired':
      return `Игровое место ${label}. Время игры закончилось.`
  }
}

/** Add a small notification sound before speech (very subtle). */
function chime() {
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.value = 880
    gain.gain.setValueAtTime(0.08, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.4)
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.4)
  } catch {
    /* ignore */
  }
}

/**
 * Voice monitor. Call `onDashboard(now)` every second from the TV page.
 * Uses server-side warning_*_sent flags so refreshes never re-speak.
 */
export function useVoiceNotifications(settings: VoiceSettings | null) {
  const processRef = useRef<(args: { dashboard: DashboardResponse; now: Date }) => void>(() => {})

  useEffect(() => {
    let speaking = false
    const queue: Array<{ text: string }> = []
    const inFlight = new Set<number>()

    function drain() {
      if (speaking) return
      const next = queue.shift()
      if (!next) {
        return
      }
      speaking = true
      speak(next.text, {
        onend: () => {
          speaking = false
          drain()
        },
      })
    }

    function fire(station: StationState, kind: '5' | '3' | '1' | 'expired') {
      if (inFlight.has(station.session_id!)) return
      inFlight.add(station.session_id!)
      chime()
      queue.push({ text: russianSpeech(station, kind) })
      drain()
      api
        .markWarnings(station.session_id!, {
          warning_5_sent: kind === '5',
          warning_3_sent: kind === '3',
          warning_1_sent: kind === '1',
          expired_sent: kind === 'expired',
        })
        .catch(() => undefined)
        .finally(() => inFlight.delete(station.session_id!))
    }

    processRef.current = (args: { dashboard: DashboardResponse; now: Date }) => {
      if (!settings || !settings.voice_enabled) return
      const { dashboard: areas, now } = args
      for (const station of areas.stations) {
        if (!station.expires_at || !station.session_id) continue
        if (!station.session_type || station.session_type === 'OPEN') continue
        const remaining = new Date(station.expires_at).getTime() - now.getTime()
        if (remaining <= 0) {
          if (settings.expired_enabled && !station.expired_sent)
            fire(station, 'expired')
        } else if (remaining <= 60_000) {
          if (settings.warning_1_enabled && !station.warning_1_sent)
            fire(station, '1')
        } else if (remaining <= 3 * 60_000) {
          if (settings.warning_3_enabled && !station.warning_3_sent)
            fire(station, '3')
        } else if (remaining <= 5 * 60_000) {
          if (settings.warning_5_enabled && !station.warning_5_sent)
            fire(station, '5')
        }
      }
    }
  }, [settings])

  return useCallback(
    (args: { dashboard: DashboardResponse; now: Date }) => processRef.current(args),
    [],
  )
}
