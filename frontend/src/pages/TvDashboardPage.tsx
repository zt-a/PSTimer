import { useCallback, useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Maximize,
  Minimize,
  MonitorPlay,
  Speaker,
  VolumeX,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { api } from '@/lib/api'
import { useDashboardStore } from '@/stores/dashboard'
import { useAuthStore } from '@/stores/auth'
import { useDashboardSocket } from '@/hooks/useDashboardSocket'
import { useNow } from '@/hooks/useNow'
import { useVoiceNotifications } from '@/hooks/useVoiceNotifications'
import { formatClock, formatDate } from '@/lib/utils'
import { unlockAudio } from '@/lib/voice'
import { StationCard } from '@/components/StationCard'
import type { VoiceSettings as VS } from '@/hooks/useVoiceNotifications'

export default function TvDashboardPage() {
  const { dashboard, connected, lastError } = useDashboardStore()
  const isAuth = useAuthStore((s) => s.isAuthenticated())
  const now = useNow()
  const [isFullscreen, setFullscreen] = useState(false)
  const [soundOn, setSoundOn] = useState(false)
  const [settings, setSettings] = useState<VS | null>(null)
  const [voiceOn, setVoiceOn] = useState(false)

  useDashboardSocket()

  // load server settings for voice gating
  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setSettings({
          voice_enabled: s.voice_enabled,
          warning_5_enabled: s.warning_5_enabled,
          warning_3_enabled: s.warning_3_enabled,
          warning_1_enabled: s.warning_1_enabled,
          expired_enabled: s.expired_enabled,
        })
        setVoiceOn(s.voice_enabled)
      })
      .catch(() => setSettings(null))
  }, [])

  const voiceTick = useVoiceNotifications(voiceOn && soundOn ? settings : null)

  // run the voice monitor every second
  useEffect(() => {
    const id = setInterval(() => {
      if (dashboard) voiceTick({ dashboard, now: new Date() })
    }, 1000)
    return () => clearInterval(id)
  }, [dashboard, voiceTick])

  // fullscreen handling
  useEffect(() => {
    const onFs = () => setFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', onFs)
    return () => document.removeEventListener('fullscreenchange', onFs)
  }, [])

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) document.exitFullscreen()
    else document.documentElement.requestFullscreen()
  }, [])

  const enableSound = () => {
    unlockAudio()
    setSoundOn(true)
  }

  // Server/client clock offset, computed once per snapshot so ticking works.
  // Without the memo, `live` is recomputed every render and cancels out the
  // `now` increment -> timers freeze.
  const live = useMemo(
    () =>
      dashboard?.server_time
        ? new Date(dashboard.server_time).getTime() - Date.now()
        : 0,
    [dashboard?.server_time],
  )

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      {/* immersive background */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-background via-[hsl(230,16%,8%)] to-black" />
        <div className="absolute -top-40 left-1/4 h-96 w-96 rounded-full bg-accent/10 blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 h-80 w-80 rounded-full bg-primary/5 blur-[100px]" />
      </div>

      {/* connection banner — only after a real outage, not during initial connect */}
      {lastError && !connected && (
        <motion.div
          initial={{ y: -40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -40, opacity: 0 }}
          className="fixed inset-x-0 top-0 z-50 flex items-center justify-center gap-2 bg-amber-500/90 py-1.5 text-xs font-semibold text-black"
        >
          <WifiOff className="h-3.5 w-3.5" />
          Соединение потеряно · переподключение…
        </motion.div>
      )}
      {connected && dashboard && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="pointer-events-none fixed inset-x-0 top-0 z-50 flex items-center justify-center"
        >
          <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-[10px] font-semibold text-emerald-400/70 uppercase tracking-widest">
            <Wifi className="h-3 w-3" /> Live
          </span>
        </motion.div>
      )}

      {/* header */}
      <header className="relative z-10 flex flex-col gap-3 px-4 pt-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-8 sm:pt-7">
        <div className="flex min-w-0 items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2 sm:gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/15 border border-accent/30 sm:h-11 sm:w-11">
              <MonitorPlay className="h-5 w-5 text-accent sm:h-6 sm:w-6" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-lg font-extrabold tracking-wide text-white sm:text-2xl">
                {dashboard?.club_name || 'PLAYSTATION CLUB'}
              </h1>
              <p className="hidden text-xs text-white/40 sm:block">
                PlayStation Club Management
              </p>
            </div>
          </div>

          {/* compact clock — mobile only */}
          <div className="shrink-0 text-right sm:hidden">
            <p className="font-mono text-2xl font-semibold tabular-nums text-white/90">
              {formatClock(now)}
            </p>
            <p className="text-[10px] capitalize text-white/40">{formatDate(now)}</p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 sm:gap-4">
          <div className="hidden text-right sm:block">
            <p className="font-mono text-4xl font-semibold tabular-nums text-white/90">
              {formatClock(now)}
            </p>
            <p className="text-xs capitalize text-white/40">{formatDate(now)}</p>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-2">
            {!soundOn ? (
              <button
                onClick={enableSound}
                className="flex items-center gap-2 rounded-xl bg-accent/20 hover:bg-accent/30 border border-accent/40 px-3 py-2 text-sm font-semibold text-white transition-colors sm:px-4"
              >
                <Speaker className="h-4 w-4" />
                <span className="hidden sm:inline">Включить звук</span>
              </button>
            ) : (
              <button
                onClick={() => setSoundOn((v) => !v)}
                className="flex items-center gap-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 px-3 py-2 text-sm font-medium text-white/70 transition-colors sm:px-4"
              >
                {voiceOn ? <Speaker className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
                <span className="hidden sm:inline">Звук вкл</span>
              </button>
            )}

            <button
              onClick={toggleFullscreen}
              className="flex items-center justify-center rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 px-3 py-2 text-white/80 transition-colors sm:px-4"
              title="Fullscreen"
            >
              {isFullscreen ? <Minimize className="h-5 w-5" /> : <Maximize className="h-5 w-5" />}
            </button>

            {isAuth && (
              <a
                href="/admin"
                className="flex items-center gap-1.5 rounded-xl bg-accent/90 hover:bg-accent px-3 py-2 text-sm font-semibold text-white transition-colors sm:px-4"
              >
                Админка
              </a>
            )}
          </div>
        </div>
      </header>

      {/* station grid */}
      <main className="relative z-10 mx-auto max-w-[1900px] px-4 py-4 sm:px-8 sm:py-8">
        {!dashboard ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
            {Array.from({ length: 9 }).map((_, i) => (
              <div
                key={i}
                className="animate-pulse rounded-2xl border border-white/5 bg-card/50 p-6 min-h-[220px]"
              />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-6 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
            {dashboard.stations.map((station) => (
              <StationCard
                key={station.id}
                station={station}
                now={now.getTime() + live}
                currency={dashboard.currency}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
