import { useMemo } from 'react'
import { formatMoney } from '@/lib/utils'
import type { HeatmapCell } from '@/types'

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

export function HourlyHeatmap({
  cells,
  currency,
}: {
  cells: HeatmapCell[]
  currency: string
}) {
  const { lookup, max } = useMemo(() => {
    const map = new Map<string, HeatmapCell>()
    let max = 0
    for (const c of cells) {
      map.set(`${c.weekday}-${c.hour}`, c)
      max = Math.max(max, Number(c.revenue))
    }
    return { lookup: map, max: max || 1 }
  }, [cells])

  const hours = Array.from({ length: 24 }, (_, i) => i)

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[720px]">
        {/* hour labels */}
        <div className="mb-1.5 flex">
          <div className="w-9 shrink-0" />
          <div
            className="grid flex-1 gap-1"
            style={{ gridTemplateColumns: 'repeat(24, minmax(0, 1fr))' }}
          >
            {hours.map((h) => (
              <div
                key={h}
                className="text-center text-[10px] tabular-nums text-white/30"
              >
                {h % 3 === 0 ? h : ''}
              </div>
            ))}
          </div>
        </div>

        {WEEKDAYS.map((day, wd) => (
          <div key={day} className="mb-1 flex items-center">
            <div className="w-9 shrink-0 text-xs font-medium text-white/40">
              {day}
            </div>
            <div
            className="grid flex-1 gap-1"
            style={{ gridTemplateColumns: 'repeat(24, minmax(0, 1fr))' }}
          >
              {hours.map((h) => {
                const cell = lookup.get(`${wd}-${h}`)
                const revenue = cell ? Number(cell.revenue) : 0
                const intensity = revenue / max
                return (
                  <div
                    key={h}
                    title={
                      cell
                        ? `${day} ${String(h).padStart(2, '0')}:00 — ${formatMoney(
                            revenue,
                            currency,
                          )} · ${cell.sessions} сес.`
                        : `${day} ${String(h).padStart(2, '0')}:00 — нет данных`
                    }
                    className="aspect-square rounded-[4px] transition-transform hover:scale-110"
                    style={{
                      background:
                        revenue > 0
                          ? `hsla(262, 83%, 58%, ${0.12 + intensity * 0.85})`
                          : 'rgba(255,255,255,0.04)',
                    }}
                  />
                )
              })}
            </div>
          </div>
        ))}

        <div className="mt-3 flex items-center justify-end gap-2 text-[10px] text-white/30">
          <span>меньше</span>
          {[0.1, 0.3, 0.55, 0.8, 1].map((v) => (
            <span
              key={v}
              className="h-3 w-3 rounded-[3px]"
              style={{ background: `hsla(262, 83%, 58%, ${0.12 + v * 0.85})` }}
            />
          ))}
          <span>больше</span>
        </div>
      </div>
    </div>
  )
}
