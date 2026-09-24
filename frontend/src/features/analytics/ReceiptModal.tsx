import { useQuery } from '@tanstack/react-query'
import { Gamepad2, Printer } from 'lucide-react'
import { api } from '@/lib/api'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { formatMoney } from '@/lib/utils'
import type { SessionHistoryItem } from '@/types'

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-white/45">{label}</span>
      <span className="tabular-nums font-medium text-white/90">{value}</span>
    </div>
  )
}

function fmt(dt: string | null): string {
  if (!dt) return '—'
  return new Date(dt).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ReceiptModal({
  open,
  sessionId,
  currency,
  clubName,
  onClose,
}: {
  open: boolean
  sessionId: number | null
  currency: string
  clubName: string
  onClose: () => void
}) {
  const q = useQuery({
    queryKey: ['receipt', sessionId],
    queryFn: () => api.getReceipt(sessionId as number),
    enabled: open && sessionId != null,
  })
  const r: SessionHistoryItem | undefined = q.data

  return (
    <Modal open={open} onClose={onClose} title="Чек">
      {!r ? (
        <div className="py-10 text-center text-sm text-white/30">Загрузка…</div>
      ) : (
        <div id="receipt-print" className="space-y-4">
          <div className="flex flex-col items-center border-b border-dashed border-white/15 pb-4 text-center">
            <div className="mb-2 flex h-11 w-11 items-center justify-center rounded-xl border border-accent/30 bg-accent/15">
              <Gamepad2 className="h-6 w-6 text-accent" />
            </div>
            <p className="font-bold tracking-wide text-white">{clubName}</p>
            <p className="text-xs text-white/40">
              Чек № {r.id} · {fmt(r.started_at)}
            </p>
          </div>

          <div className="divide-y divide-white/5">
            <Row label="Станция" value={`${r.station_name} (№${r.station_number})`} />
            <Row label="Тариф" value={r.tariff_name} />
            <Row label="Тип" value={r.type === 'OPEN' ? 'Открытая' : 'Фиксированная'} />
            <Row label="Начало" value={fmt(r.started_at)} />
            <Row label="Окончание" value={fmt(r.ended_at)} />
            <Row
              label="Длительность"
              value={`${Math.floor(r.duration_minutes / 60)} ч ${r.duration_minutes % 60} мин`}
            />
            {r.total_paused_seconds > 0 && (
              <Row
                label="Пауза"
                value={`${Math.floor(r.total_paused_seconds / 60)} мин`}
              />
            )}
            <Row label="Ставка" value={formatMoney(r.price_snapshot, `${currency}/час`)} />
            <Row label="Статус" value={r.status} />
          </div>

          <div className="flex items-center justify-between rounded-xl border border-accent/25 bg-accent/10 px-4 py-3">
            <span className="text-sm font-medium text-white/70">Итого к оплате</span>
            <span className="text-xl font-bold tabular-nums text-white">
              {formatMoney(r.amount ?? 0, currency)}
            </span>
          </div>

          <Button
            variant="secondary"
            className="w-full print:hidden"
            onClick={() => window.print()}
          >
            <Printer className="h-4 w-4" /> Распечатать
          </Button>
        </div>
      )}
    </Modal>
  )
}
