import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3,
  CalendarDays,
  Gamepad2,
  History,
  LogOut,
  Monitor,
  Play,
  Plus,
  Settings as SettingsIcon,
  Trash2,
  TrendingUp,
  Users,
} from 'lucide-react'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { useDashboardStore } from '@/stores/dashboard'
import { useDashboardSocket } from '@/hooks/useDashboardSocket'
import { useNow } from '@/hooks/useNow'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ToastViewport, type ToastData } from '@/components/ui/Toast'
import { formatMoney } from '@/lib/utils'
import type { Station, StationState, Tariff } from '@/types'
import { StartSessionModal } from '@/features/admin/StartSessionModal'
import { ExtendModal } from '@/features/admin/ExtendModal'
import { StopModal } from '@/features/admin/StopModal'
import { TariffEditorModal } from '@/features/admin/TariffEditorModal'
import { StationEditorModal } from '@/features/admin/StationEditorModal'
import { SettingsPanel } from '@/features/admin/SettingsPanel'
import { StationRow } from '@/features/admin/StationRow'

// Charts pull in recharts — load them only when the analytics tabs are opened
// so the TV kiosk bundle stays lean.
const AnalyticsTab = lazy(() =>
  import('@/features/analytics/AnalyticsTab').then((m) => ({ default: m.AnalyticsTab })),
)
const HistoryTab = lazy(() =>
  import('@/features/analytics/HistoryTab').then((m) => ({ default: m.HistoryTab })),
)

const TABS = [
  ['overview', 'Обзор', Monitor],
  ['analytics', 'Аналитика', BarChart3],
  ['history', 'История', History],
  ['tariffs', 'Тарифы', TrendingUp],
  ['stations', 'Станции', Users],
  ['settings', 'Настройки', SettingsIcon],
] as const

export default function AdminPage() {
  const navigate = useNavigate()
  const logout = useAuthStore((s) => s.logout)
  const { dashboard, setDashboard } = useDashboardStore()
  const now = useNow()
  useDashboardSocket()

  // Tab state
  const [tab, setTab] = useState<
    'overview' | 'analytics' | 'history' | 'tariffs' | 'stations' | 'settings'
  >('overview')

  // Modal state
  const [startFor, setStartFor] = useState<StationState | null>(null)
  const [extendFor, setExtendFor] = useState<StationState | null>(null)
  const [stopFor, setStopFor] = useState<StationState | null>(null)
  const [tariffEditor, setTariffEditor] = useState<{ open: boolean; tariff: Tariff | null }>({
    open: false,
    tariff: null,
  })
  const [stationEditor, setStationEditor] = useState<{ open: boolean; station: Station | null }>({
    open: false,
    station: null,
  })

  const [toasts, setToasts] = useState<ToastData[]>([])
  const notify = useCallback((message: string, type: 'success' | 'error' = 'success') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, message, type }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3000)
  }, [])

  // Data
  const tariffsQuery = useQuery({ queryKey: ['tariffs'], queryFn: api.getTariffs })
  const stationsQuery = useQuery({ queryKey: ['stations'], queryFn: api.getStations })
  const settingsQuery = useQuery({ queryKey: ['settings'], queryFn: api.getSettings })
  const reportQuery = useQuery({ queryKey: ['daily'], queryFn: api.getDailyReport, refetchInterval: 60000 })

  const tariffs = tariffsQuery.data ?? []
  const currency = settingsQuery.data?.currency ?? 'сом'
  // Server/client clock offset, computed once per snapshot so ticking works.
  const live = useMemo(
    () =>
      dashboard?.server_time
        ? new Date(dashboard.server_time).getTime() - Date.now()
        : 0,
    [dashboard?.server_time],
  )
  const nowMs = now.getTime() + live

  // mutations that force a dashboard refetch (WS usually covers it, belt+braces)
  const invalidate = () => {
    api
      .getDashboard()
      .then(setDashboard)
      .catch(() => undefined)
  }
  useEffect(() => {
    invalidate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startFor, extendFor, stopFor])

  const stats = useMemo(() => {
    const stations = dashboard?.stations ?? []
    const active = stations.filter(
      (s) => s.status !== null && s.session_id && s.status !== 'PAUSED',
    ).length
    const free = stations.filter((s) => s.status === null || !s.session_id).length
    const expired = stations.filter((s) => s.status === 'EXPIRED').length
    return { total: stations.length, active, free, expired }
  }, [dashboard])

  const handleDeleteTariff = async (t: Tariff) => {
    if (!window.confirm(`Удалить тариф «${t.name}»?`)) return
    try {
      await api.deleteTariff(t.id)
      notify('Тариф удалён')
      tariffsQuery.refetch()
    } catch (e: any) {
      notify(e.message, 'error')
    }
  }

  const handleDeleteStation = async (s: Station) => {
    if (!window.confirm(`Удалить станцию «${s.name}»?`)) return
    try {
      await api.deleteStation(s.id)
      notify('Станция удалена')
      stationsQuery.refetch()
    } catch (e: any) {
      notify(e.message, 'error')
    }
  }

  const handleToggleStation = async (s: Station) => {
    try {
      await api.updateStation(s.id, { is_active: !s.is_active })
      stationsQuery.refetch()
    } catch (e: any) {
      notify(e.message, 'error')
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-background to-black" />
        <div className="absolute -top-40 left-1/4 h-96 w-96 rounded-full bg-accent/10 blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 h-80 w-80 rounded-full bg-primary/5 blur-[100px]" />
      </div>

      {/* top bar */}
      <header className="relative z-10 sticky top-0 border-b border-white/5 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto max-w-[1500px] px-3 py-3 sm:px-6">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2 sm:gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent/15 border border-accent/30">
                <Gamepad2 className="h-5 w-5 text-accent" />
              </div>
              <h1 className="truncate text-base font-bold text-white sm:text-lg">
                {dashboard?.club_name || 'PS Club'}
              </h1>
            </div>

            <nav className="hidden items-center gap-1 md:flex">
              {TABS.map(([key, label, Icon]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    tab === key
                      ? 'bg-accent/15 text-accent'
                      : 'text-white/50 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              ))}
            </nav>

            <div className="flex shrink-0 items-center gap-1 sm:gap-2">
              <Button variant="outline" size="sm" onClick={() => navigate('/')}>
                <Monitor className="h-4 w-4" />
                <span className="hidden sm:inline">TV</span>
              </Button>
              <Button variant="ghost" size="sm" onClick={logout}>
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Выйти</span>
              </Button>
            </div>
          </div>

          {/* mobile tab bar */}
          <nav className="no-scrollbar -mx-3 mt-2 flex gap-1 overflow-x-auto px-3 sm:-mx-6 sm:px-6 md:hidden">
            {TABS.map(([key, label, Icon]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  tab === key
                    ? 'bg-accent/15 text-accent'
                    : 'text-white/50 hover:bg-white/5 hover:text-white'
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-[1500px] px-3 py-4 sm:px-6 sm:py-6">
        {/* overview */}
        {tab === 'overview' && (
          <div className="space-y-6">
            {/* stat cards */}
            <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
              {[
                {
                  label: 'Выручка сегодня',
                  value: formatMoney(reportQuery.data?.total_revenue ?? 0, currency),
                  icon: TrendingUp,
                  color: 'text-emerald-400',
                },
                {
                  label: 'Активные сессии',
                  value: String(stats.active),
                  icon: Play,
                  color: 'text-accent',
                },
                {
                  label: 'Свободные места',
                  value: String(stats.free),
                  icon: Users,
                  color: 'text-sky-300',
                },
                {
                  label: 'Сессий завершено',
                  value: String(reportQuery.data?.completed_sessions ?? 0),
                  icon: CalendarDays,
                  color: 'text-white/70',
                },
              ].map((s) => (
                <Card key={s.label} className="p-4 sm:p-5">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-[11px] uppercase tracking-wider text-white/40 sm:text-xs">{s.label}</p>
                      <p className="mt-1.5 truncate text-xl font-bold tabular-nums text-white sm:text-2xl">{s.value}</p>
                    </div>
                    <s.icon className={`h-6 w-6 shrink-0 ${s.color}`} />
                  </div>
                </Card>
              ))}
            </div>

            {stats.expired > 0 && (
              <div className="flex items-center gap-2 rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
                ⚠ {stats.expired} станц. с истекшим временем — завершите сессии
              </div>
            )}

            {/* stations list */}
            <div className="space-y-3">
              {!dashboard ? (
                <div className="space-y-3">
                  {Array.from({ length: 7 }).map((_, i) => (
                    <div key={i} className="h-16 animate-pulse rounded-2xl bg-card/40" />
                  ))}
                </div>
              ) : (
                dashboard.stations.map((station) => (
                  <StationRow
                    key={station.id}
                    station={station}
                    now={nowMs}
                    currency={currency}
                    onStart={(s) => setStartFor(s)}
                    onExtend={(s) => setExtendFor(s)}
                    onPause={async (s) => {
                      try {
                        await api.pauseSession(s.session_id!)
                        notify('Сессия на паузе')
                      } catch (e: any) {
                        notify(e.message, 'error')
                      }
                    }}
                    onResume={async (s) => {
                      try {
                        await api.resumeSession(s.session_id!)
                        notify('Сессия возобновлена')
                      } catch (e: any) {
                        notify(e.message, 'error')
                      }
                    }}
                    onStop={(s) => setStopFor(s)}
                  />
                ))
              )}
            </div>
          </div>
        )}

        {/* analytics */}
        {tab === 'analytics' && (
          <Suspense fallback={<TabLoader />}>
            <AnalyticsTab currency={currency} />
          </Suspense>
        )}

        {/* history */}
        {tab === 'history' && (
          <Suspense fallback={<TabLoader />}>
            <HistoryTab
              currency={currency}
              clubName={dashboard?.club_name || 'PS Club'}
            />
          </Suspense>
        )}

        {/* tariffs */}
        {tab === 'tariffs' && (
          <div className="max-w-3xl space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">Тарифы</h2>
              <Button onClick={() => setTariffEditor({ open: true, tariff: null })}>
                <Plus className="h-4 w-4" /> Новый тариф
              </Button>
            </div>

            <div className="space-y-3">
              {tariffs.length === 0 && (
                <Card className="text-sm text-white/40">Пока нет тарифов. Создайте первый.</Card>
              )}
              {tariffs.map((t) => (
                <Card key={t.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-white">{t.name}</p>
                    <p className="text-xs text-white/40">
                      {formatMoney(t.price_per_hour, `${currency}/час`)} · посекундно
                    </p>
                  </div>
                  <div className="flex items-center justify-between gap-2 sm:justify-end">
                    <span
                      className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase ${
                        t.is_active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-white/5 text-white/40'
                      }`}
                    >
                      {t.is_active ? 'Активен' : 'Выключен'}
                    </span>
                    <div className="flex gap-2">
                      <Button variant="secondary" size="sm" onClick={() => setTariffEditor({ open: true, tariff: t })}>
                        Изменить
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDeleteTariff(t)}>
                        <Trash2 className="h-4 w-4 text-danger" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* stations management */}
        {tab === 'stations' && (
          <div className="max-w-3xl space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">Станции</h2>
              <Button onClick={() => setStationEditor({ open: true, station: null })}>
                <Plus className="h-4 w-4" /> Новая станция
              </Button>
            </div>
            <div className="space-y-3">
              {stationsQuery.data?.map((s) => (
                <Card key={s.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-white">
                      {s.name}{' '}
                      <span className="ml-1 rounded bg-white/5 px-2 py-0.5 text-[10px] text-white/40">{s.type}</span>
                    </p>
                    <p className="text-xs text-white/40">№ {s.number}</p>
                  </div>
                  <div className="flex items-center justify-between gap-2 sm:justify-end">
                    <button
                      onClick={() => handleToggleStation(s)}
                      className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                        s.is_active
                          ? 'bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25'
                          : 'bg-white/5 text-white/40 hover:bg-white/10'
                      }`}
                    >
                      {s.is_active ? 'Активна' : 'Выключена'}
                    </button>
                    <div className="flex gap-2">
                      <Button variant="secondary" size="sm" onClick={() => setStationEditor({ open: true, station: s })}>
                        Изменить
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => handleDeleteStation(s)}>
                        <Trash2 className="h-4 w-4 text-danger" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* settings */}
        {tab === 'settings' && (
          <div className="max-w-2xl">
            <h2 className="mb-4 text-lg font-bold text-white">Настройки клуба</h2>
            <Card>
              <SettingsPanel settings={settingsQuery.data ?? null} onDone={notify} />
            </Card>
          </div>
        )}
      </main>

      {/* modals */}
      <StartSessionModal
        open={!!startFor}
        station={startFor}
        tariffs={tariffs}
        currency={currency}
        onClose={() => setStartFor(null)}
        onDone={(m) => notify(m)}
      />
      <ExtendModal
        open={!!extendFor}
        station={extendFor}
        onClose={() => setExtendFor(null)}
        onDone={(m) => notify(m)}
      />
      <StopModal
        open={!!stopFor}
        station={stopFor}
        dashboard={dashboard}
        onClose={() => setStopFor(null)}
        onDone={(m) => notify(m)}
      />
      <TariffEditorModal
        open={tariffEditor.open}
        tariff={tariffEditor.tariff}
        onClose={() => setTariffEditor({ open: false, tariff: null })}
        onDone={(m) => {
          notify(m)
          tariffsQuery.refetch()
        }}
      />
      <StationEditorModal
        open={stationEditor.open}
        station={stationEditor.station}
        onClose={() => setStationEditor({ open: false, station: null })}
        onDone={(m) => {
          notify(m)
          stationsQuery.refetch()
        }}
      />

      <ToastViewport toasts={toasts} />
    </div>
  )
}

function TabLoader() {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-28 animate-pulse rounded-2xl bg-card/40" />
      ))}
      <div className="col-span-2 h-80 animate-pulse rounded-2xl bg-card/40 lg:col-span-5" />
    </div>
  )
}
