import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  CalendarRange,
  Coins,
  Gamepad2,
  Gauge,
  ReceiptText,
  TrendingDown,
  TrendingUp,
  Users,
} from 'lucide-react'
import { api } from '@/lib/api'
import { Card } from '@/components/ui/Card'
import { formatMoney } from '@/lib/utils'
import type { AnalyticsQuery, PeriodKey } from '@/types'
import {
  RevenueAreaChart,
  SessionsBarChart,
  StationBarChart,
  TariffDonut,
} from './charts'
import { HourlyHeatmap } from './Heatmap'

const PERIODS: { key: PeriodKey; label: string }[] = [
  { key: 'today', label: 'Сегодня' },
  { key: 'week', label: 'Неделя' },
  { key: 'month', label: 'Месяц' },
  { key: 'year', label: 'Год' },
  { key: 'custom', label: 'Период' },
]

function formatPlay(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h === 0) return `${m} мин`
  return `${h} ч ${m} мин`
}

function Delta({ value }: { value: number | null }) {
  if (value === null || value === undefined) return null
  const up = value >= 0
  const Icon = up ? TrendingUp : TrendingDown
  return (
    <span
      className={`mt-1 inline-flex items-center gap-1 text-xs font-medium ${
        up ? 'text-emerald-400' : 'text-danger'
      }`}
    >
      <Icon className="h-3 w-3" />
      {up ? '+' : ''}
      {value.toFixed(1)}%
      <span className="hidden text-white/30 sm:inline">к пред. периоду</span>
    </span>
  )
}

function Kpi({
  label,
  value,
  icon: Icon,
  color,
  delta,
}: {
  label: string
  value: string
  icon: any
  color: string
  delta?: number | null
}) {
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[11px] uppercase tracking-wider text-white/40 sm:text-xs">{label}</p>
          <p className="mt-1.5 truncate text-xl font-bold tabular-nums text-white sm:text-2xl">
            {value}
          </p>
          {delta !== undefined && <Delta value={delta} />}
        </div>
        <div className={`shrink-0 rounded-xl bg-white/5 p-2 sm:p-2.5 ${color}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </Card>
  )
}

function ChartCard({
  title,
  subtitle,
  children,
  className = '',
}: {
  title: string
  subtitle?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <Card className={`p-4 sm:p-5 ${className}`}>
      <div className="mb-4">
        <h3 className="font-semibold text-white">{title}</h3>
        {subtitle && <p className="text-xs text-white/40">{subtitle}</p>}
      </div>
      {children}
    </Card>
  )
}

export function AnalyticsTab({ currency }: { currency: string }) {
  const [period, setPeriod] = useState<PeriodKey>('month')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const query: AnalyticsQuery = useMemo(() => {
    if (period === 'custom') {
      if (from && to) return { date_from: from, date_to: to }
      return {}
    }
    return { period }
  }, [period, from, to])

  const ready = period !== 'custom' || (!!from && !!to)

  const summaryQ = useQuery({
    queryKey: ['analytics', 'summary', query],
    queryFn: () => api.getSummary(query),
    enabled: ready,
  })
  const revenueQ = useQuery({
    queryKey: ['analytics', 'revenue', query],
    queryFn: () => api.getRevenueSeries(query),
    enabled: ready,
  })
  const stationsQ = useQuery({
    queryKey: ['analytics', 'stations', query],
    queryFn: () => api.getStationStats(query),
    enabled: ready,
  })
  const tariffsQ = useQuery({
    queryKey: ['analytics', 'tariffs', query],
    queryFn: () => api.getTariffStats(query),
    enabled: ready,
  })
  const heatmapQ = useQuery({
    queryKey: ['analytics', 'heatmap', query],
    queryFn: () => api.getHeatmap(query),
    enabled: ready,
  })

  const s = summaryQ.data
  const series = (revenueQ.data?.points ?? []).map((p) => ({
    label: p.label,
    revenue: Number(p.revenue),
    sessions: p.sessions,
  }))
  const stations = (stationsQ.data ?? [])
    .filter((x) => Number(x.revenue) > 0)
    .map((x) => ({ name: x.name, revenue: Number(x.revenue) }))
  const tariffs = (tariffsQ.data ?? [])
    .filter((x) => Number(x.revenue) > 0)
    .map((x) => ({ name: x.name, revenue: Number(x.revenue) }))

  return (
    <div className="space-y-6">
      {/* period selector */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="no-scrollbar flex max-w-full items-center gap-1 overflow-x-auto rounded-xl border border-white/10 bg-white/5 p-1">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                period === p.key
                  ? 'bg-accent text-white shadow-glow'
                  : 'text-white/50 hover:text-white'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        {period === 'custom' && (
          <div className="flex w-full items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 sm:w-auto">
            <CalendarRange className="h-4 w-4 shrink-0 text-white/40" />
            <input
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none [color-scheme:dark]"
            />
            <span className="text-white/30">—</span>
            <input
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none [color-scheme:dark]"
            />
          </div>
        )}
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
        <Kpi
          label="Выручка"
          value={formatMoney(s?.revenue ?? 0, currency)}
          icon={Coins}
          color="text-emerald-400"
          delta={s?.revenue_delta}
        />
        <Kpi
          label="Сессий"
          value={String(s?.sessions ?? 0)}
          icon={Gamepad2}
          color="text-accent"
          delta={s?.sessions_delta}
        />
        <Kpi
          label="Средний чек"
          value={formatMoney(s?.avg_check ?? 0, currency)}
          icon={ReceiptText}
          color="text-sky-300"
          delta={s?.avg_check_delta}
        />
        <Kpi
          label="Отыграно"
          value={formatPlay(s?.play_seconds ?? 0)}
          icon={Users}
          color="text-white/70"
          delta={s?.play_seconds_delta}
        />
        <Kpi
          label="Загрузка"
          value={`${(s?.utilization ?? 0).toFixed(1)}%`}
          icon={Gauge}
          color="text-amber-400"
        />
      </div>

      {/* revenue + sessions */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <ChartCard
          title="Выручка"
          subtitle={`Грануляция: ${revenueQ.data?.bucket ?? '—'}`}
          className="xl:col-span-2"
        >
          {series.length ? (
            <RevenueAreaChart data={series} currency={currency} />
          ) : (
            <Empty />
          )}
        </ChartCard>
        <ChartCard title="Сессии" subtitle="Количество завершённых сессий">
          {series.length ? (
            <SessionsBarChart data={series} currency={currency} />
          ) : (
            <Empty />
          )}
        </ChartCard>
      </div>

      {/* stations + tariffs */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <ChartCard title="Выручка по станциям" className="xl:col-span-2">
          {stations.length ? (
            <StationBarChart data={stations} currency={currency} />
          ) : (
            <Empty />
          )}
        </ChartCard>
        <ChartCard title="Выручка по тарифам">
          {tariffs.length ? (
            <TariffDonut data={tariffs} currency={currency} />
          ) : (
            <Empty />
          )}
        </ChartCard>
      </div>

      {/* heatmap */}
      <ChartCard
        title="Загруженность по часам"
        subtitle="Выручка по дням недели и часам"
      >
        {heatmapQ.data?.length ? (
          <HourlyHeatmap cells={heatmapQ.data} currency={currency} />
        ) : (
          <Empty />
        )}
      </ChartCard>
    </div>
  )
}

function Empty() {
  return (
    <div className="flex h-[220px] items-center justify-center text-sm text-white/30">
      Нет данных за выбранный период
    </div>
  )
}
