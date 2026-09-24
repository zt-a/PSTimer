import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  ListFilter,
} from 'lucide-react'
import { api } from '@/lib/api'
import { Card } from '@/components/ui/Card'
import { formatMoney } from '@/lib/utils'
import type { AnalyticsQuery, PeriodKey } from '@/types'
import { ReceiptModal } from './ReceiptModal'

const PERIODS: { key: PeriodKey; label: string }[] = [
  { key: 'today', label: 'Сегодня' },
  { key: 'week', label: 'Неделя' },
  { key: 'month', label: 'Месяц' },
  { key: 'custom', label: 'Период' },
]

const STATUSES = ['ACTIVE', 'OPEN', 'PAUSED', 'EXPIRED', 'COMPLETED'] as const

const STATUS_LABEL: Record<string, string> = {
  ACTIVE: 'Активна',
  OPEN: 'Открыта',
  PAUSED: 'Пауза',
  EXPIRED: 'Истекла',
  COMPLETED: 'Завершена',
}

const STATUS_STYLE: Record<string, string> = {
  ACTIVE: 'bg-accent/15 text-accent',
  OPEN: 'bg-sky-500/15 text-sky-300',
  PAUSED: 'bg-amber-500/15 text-amber-400',
  EXPIRED: 'bg-danger/15 text-danger',
  COMPLETED: 'bg-emerald-500/15 text-emerald-400',
}

function fmt(dt: string | null): string {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function Pagination({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number
  pageSize: number
  total: number
  onPage: (p: number) => void
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 pt-2 text-sm text-white/50">
      <span>
        {total} записей · стр. {page} из {pages}
      </span>
      <div className="flex gap-2">
        <button
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="rounded-lg border border-white/10 bg-white/5 p-1.5 disabled:opacity-30 hover:bg-white/10"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
          className="rounded-lg border border-white/10 bg-white/5 p-1.5 disabled:opacity-30 hover:bg-white/10"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

export function HistoryTab({
  currency,
  clubName,
}: {
  currency: string
  clubName: string
}) {
  const [view, setView] = useState<'sessions' | 'payments'>('sessions')
  const [period, setPeriod] = useState<PeriodKey>('month')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [stationId, setStationId] = useState<number | ''>('')
  const [status, setStatus] = useState<string>('')
  const [page, setPage] = useState(1)
  const [receiptId, setReceiptId] = useState<number | null>(null)

  const stationsQuery = useQuery({ queryKey: ['stations'], queryFn: api.getStations })
  const pageSize = 15

  const baseQuery: AnalyticsQuery = useMemo(() => {
    if (period === 'custom') {
      return from && to ? { date_from: from, date_to: to } : {}
    }
    return { period }
  }, [period, from, to])

  const ready = period !== 'custom' || (!!from && !!to)

  const sessionsQ = useQuery({
    queryKey: ['history', 'sessions', baseQuery, stationId, status, page],
    queryFn: () =>
      api.getSessionHistory({
        ...baseQuery,
        station_id: stationId === '' ? undefined : stationId,
        status: status || undefined,
        page,
        page_size: pageSize,
      }),
    enabled: ready && view === 'sessions',
  })

  const paymentsQ = useQuery({
    queryKey: ['history', 'payments', baseQuery, page],
    queryFn: () => api.getPayments({ ...baseQuery, page, page_size: pageSize }),
    enabled: ready && view === 'payments',
  })

  const resetPage = () => setPage(1)

  const th =
    'px-2 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-white/40 sm:px-4'
  const td = 'px-2 py-3 text-sm text-white/80 sm:px-4'

  return (
    <div className="space-y-5">
      {/* controls */}
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <div className="flex items-center gap-1 rounded-xl border border-white/10 bg-white/5 p-1">
          {(['sessions', 'payments'] as const).map((v) => (
            <button
              key={v}
              onClick={() => {
                setView(v)
                resetPage()
              }}
              className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                view === v ? 'bg-accent text-white' : 'text-white/50 hover:text-white'
              }`}
            >
              {v === 'sessions' ? 'Сессии' : 'Платежи'}
            </button>
          ))}
        </div>

        <div className="no-scrollbar flex max-w-full items-center gap-1 overflow-x-auto rounded-xl border border-white/10 bg-white/5 p-1">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => {
                setPeriod(p.key)
                resetPage()
              }}
              className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                period === p.key ? 'bg-white/10 text-white' : 'text-white/50 hover:text-white'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {period === 'custom' && (
          <div className="flex w-full items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 sm:w-auto">
            <input
              type="date"
              value={from}
              onChange={(e) => {
                setFrom(e.target.value)
                resetPage()
              }}
              className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none [color-scheme:dark]"
            />
            <span className="text-white/30">—</span>
            <input
              type="date"
              value={to}
              onChange={(e) => {
                setTo(e.target.value)
                resetPage()
              }}
              className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none [color-scheme:dark]"
            />
          </div>
        )}

        {view === 'sessions' && (
          <div className="flex w-full items-center gap-2 sm:w-auto">
            <div className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 sm:flex-none">
              <ListFilter className="h-4 w-4 shrink-0 text-white/40" />
              <select
                value={stationId}
                onChange={(e) => {
                  setStationId(e.target.value === '' ? '' : Number(e.target.value))
                  resetPage()
                }}
                className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none [&>option]:bg-card"
              >
                <option value="">Все станции</option>
                {stationsQuery.data?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value)
                resetPage()
              }}
              className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none [&>option]:bg-card sm:flex-none"
            >
              <option value="">Все статусы</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* sessions */}
      {view === 'sessions' && (
        <Card className="overflow-hidden p-0">
          {/* mobile cards */}
          <div className="divide-y divide-white/5 md:hidden">
            {sessionsQ.data?.items.map((s) => (
              <div key={s.id} className="flex items-center gap-3 p-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="font-medium text-white">{s.station_name}</span>
                    <span className="text-xs text-white/30">№{s.station_number}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                        STATUS_STYLE[s.status] ?? 'bg-white/5 text-white/50'
                      }`}
                    >
                      {STATUS_LABEL[s.status] ?? s.status}
                    </span>
                  </div>
                  <p className="mt-1 truncate text-xs text-white/40">
                    {fmt(s.started_at)} · {Math.floor(s.duration_minutes / 60)}ч{' '}
                    {s.duration_minutes % 60}м · {s.tariff_name}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="tabular-nums font-semibold text-white">
                    {s.amount != null ? formatMoney(s.amount, currency) : '—'}
                  </p>
                  <button
                    onClick={() => setReceiptId(s.id)}
                    className="mt-1 inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-white/60 hover:bg-white/10 hover:text-white"
                  >
                    <FileText className="h-3.5 w-3.5" /> Чек
                  </button>
                </div>
              </div>
            ))}
            {sessionsQ.data && sessionsQ.data.items.length === 0 && (
              <div className="px-4 py-12 text-center text-sm text-white/30">
                Нет сессий за выбранный период
              </div>
            )}
          </div>

          {/* desktop table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[820px]">
              <thead className="border-b border-white/5 bg-white/[0.02]">
                <tr>
                  <th className={th}>Станция</th>
                  <th className={`${th} hidden md:table-cell`}>Тариф</th>
                  <th className={`${th} hidden lg:table-cell`}>Тип</th>
                  <th className={th}>Начало</th>
                  <th className={`${th} hidden md:table-cell`}>Конец</th>
                  <th className={`${th} hidden sm:table-cell`}>Длит.</th>
                  <th className={th}>Сумма</th>
                  <th className={th}>Статус</th>
                  <th className={th}></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {sessionsQ.data?.items.map((s) => (
                  <tr key={s.id} className="transition-colors hover:bg-white/[0.03]">
                    <td className={td}>
                      <span className="font-medium text-white">{s.station_name}</span>
                      <span className="ml-1.5 text-xs text-white/30">№{s.station_number}</span>
                    </td>
                    <td className={`${td} hidden md:table-cell`}>{s.tariff_name}</td>
                    <td className={`${td} hidden lg:table-cell`}>
                      <span className="text-xs text-white/50">
                        {s.type === 'OPEN' ? 'Открытая' : 'Фикс.'}
                      </span>
                    </td>
                    <td className={`${td} tabular-nums text-white/60`}>{fmt(s.started_at)}</td>
                    <td className={`${td} hidden tabular-nums text-white/60 md:table-cell`}>{fmt(s.ended_at)}</td>
                    <td className={`${td} hidden tabular-nums sm:table-cell`}>
                      {Math.floor(s.duration_minutes / 60)}ч {s.duration_minutes % 60}м
                    </td>
                    <td className={`${td} tabular-nums font-semibold text-white`}>
                      {s.amount != null ? formatMoney(s.amount, currency) : '—'}
                    </td>
                    <td className={td}>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                          STATUS_STYLE[s.status] ?? 'bg-white/5 text-white/50'
                        }`}
                      >
                        {STATUS_LABEL[s.status] ?? s.status}
                      </span>
                    </td>
                    <td className={td}>
                      <button
                        onClick={() => setReceiptId(s.id)}
                        className="rounded-lg border border-white/10 bg-white/5 p-1.5 text-white/60 hover:bg-white/10 hover:text-white"
                        title="Чек"
                      >
                        <FileText className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
                {sessionsQ.data && sessionsQ.data.items.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-12 text-center text-sm text-white/30">
                      Нет сессий за выбранный период
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {sessionsQ.data && (
            <div className="border-t border-white/5 px-3 py-3 sm:px-4">
              <Pagination
                page={page}
                pageSize={pageSize}
                total={sessionsQ.data.total}
                onPage={setPage}
              />
            </div>
          )}
        </Card>
      )}

      {/* payments */}
      {view === 'payments' && (
        <Card className="overflow-hidden p-0">
          <div className="flex items-center justify-between gap-2 border-b border-white/5 px-3 py-3 sm:px-4">
            <span className="text-sm text-white/50">История оплат</span>
            <span className="text-sm">
              Итого:{' '}
              <span className="font-bold tabular-nums text-emerald-400">
                {formatMoney(paymentsQ.data?.total_amount ?? 0, currency)}
              </span>
            </span>
          </div>

          {/* mobile cards */}
          <div className="divide-y divide-white/5 md:hidden">
            {paymentsQ.data?.items.map((p) => (
              <div key={p.id} className="flex items-center gap-3 p-3">
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-white">{p.station_name}</p>
                  <p className="mt-0.5 truncate text-xs text-white/40">
                    {fmt(p.created_at)} · {p.tariff_name}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <span className="tabular-nums font-semibold text-emerald-400">
                    +{formatMoney(p.amount, currency)}
                  </span>
                  <button
                    onClick={() => setReceiptId(p.session_id)}
                    className="rounded-lg border border-white/10 bg-white/5 p-1.5 text-white/60 hover:bg-white/10 hover:text-white"
                    title="Чек"
                  >
                    <FileText className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
            {paymentsQ.data && paymentsQ.data.items.length === 0 && (
              <div className="px-4 py-12 text-center text-sm text-white/30">
                Нет платежей за выбранный период
              </div>
            )}
          </div>

          {/* desktop table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[640px]">
              <thead className="border-b border-white/5 bg-white/[0.02]">
                <tr>
                  <th className={th}>Время</th>
                  <th className={th}>Станция</th>
                  <th className={`${th} hidden md:table-cell`}>Тариф</th>
                  <th className={`${th} hidden sm:table-cell`}>Сессия</th>
                  <th className={th}>Сумма</th>
                  <th className={th}></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {paymentsQ.data?.items.map((p) => (
                  <tr key={p.id} className="transition-colors hover:bg-white/[0.03]">
                    <td className={`${td} tabular-nums text-white/60`}>
                      {fmt(p.created_at)}
                    </td>
                    <td className={td}>
                      <span className="font-medium text-white">{p.station_name}</span>
                    </td>
                    <td className={`${td} hidden md:table-cell`}>{p.tariff_name}</td>
                    <td className={`${td} hidden tabular-nums text-white/40 sm:table-cell`}>#{p.session_id}</td>
                    <td className={`${td} tabular-nums font-semibold text-emerald-400`}>
                      +{formatMoney(p.amount, currency)}
                    </td>
                    <td className={td}>
                      <button
                        onClick={() => setReceiptId(p.session_id)}
                        className="rounded-lg border border-white/10 bg-white/5 p-1.5 text-white/60 hover:bg-white/10 hover:text-white"
                        title="Чек"
                      >
                        <FileText className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
                {paymentsQ.data && paymentsQ.data.items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-sm text-white/30">
                      Нет платежей за выбранный период
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {paymentsQ.data && (
            <div className="border-t border-white/5 px-3 py-3 sm:px-4">
              <Pagination
                page={page}
                pageSize={pageSize}
                total={paymentsQ.data.total}
                onPage={setPage}
              />
            </div>
          )}
        </Card>
      )}

      <ReceiptModal
        open={receiptId != null}
        sessionId={receiptId}
        currency={currency}
        clubName={clubName}
        onClose={() => setReceiptId(null)}
      />
    </div>
  )
}
