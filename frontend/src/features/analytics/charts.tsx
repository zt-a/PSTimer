import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatMoney } from '@/lib/utils'

export const CHART_COLORS = [
  'hsl(262, 83%, 58%)',
  'hsl(158, 64%, 52%)',
  'hsl(199, 89%, 48%)',
  'hsl(38, 92%, 50%)',
  'hsl(330, 70%, 60%)',
  'hsl(174, 60%, 45%)',
  'hsl(0, 72%, 51%)',
  'hsl(280, 65%, 62%)',
]

const AXIS = { fill: 'rgba(255,255,255,0.4)', fontSize: 11 }
const GRID = 'rgba(255,255,255,0.06)'

function compact(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(value >= 10_000 ? 0 : 1)}k`
  return String(Math.round(value))
}

function ChartTooltip({ active, payload, label, currency }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-white/10 bg-card/95 px-3 py-2 text-xs shadow-glass backdrop-blur-xl">
      {label !== undefined && <p className="mb-1 font-medium text-white/60">{label}</p>}
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 text-white">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: p.color || p.fill }}
          />
          <span className="text-white/60">{p.name}:</span>
          <span className="tabular-nums font-semibold">
            {p.dataKey === 'revenue'
              ? formatMoney(Number(p.value), currency)
              : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export function RevenueAreaChart({
  data,
  currency,
}: {
  data: { label: string; revenue: number }[]
  currency: string
}) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <defs>
          <linearGradient id="revGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(262, 83%, 58%)" stopOpacity={0.45} />
            <stop offset="100%" stopColor="hsl(262, 83%, 58%)" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis
          dataKey="label"
          tick={AXIS}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
          minTickGap={24}
        />
        <YAxis
          tick={AXIS}
          axisLine={false}
          tickLine={false}
          width={44}
          tickFormatter={compact}
        />
        <Tooltip
          content={<ChartTooltip currency={currency} />}
          cursor={{ stroke: 'rgba(255,255,255,0.12)' }}
        />
        <Area
          type="monotone"
          dataKey="revenue"
          name="Выручка"
          stroke="hsl(262, 83%, 58%)"
          strokeWidth={2.5}
          fill="url(#revGradient)"
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function SessionsBarChart({
  data,
  currency,
}: {
  data: { label: string; sessions: number }[]
  currency: string
}) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} vertical={false} />
        <XAxis
          dataKey="label"
          tick={AXIS}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
          minTickGap={24}
        />
        <YAxis
          tick={AXIS}
          axisLine={false}
          tickLine={false}
          width={44}
          allowDecimals={false}
        />
        <Tooltip
          content={<ChartTooltip currency={currency} />}
          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
        />
        <Bar
          dataKey="sessions"
          name="Сессии"
          fill="hsl(158, 64%, 52%)"
          radius={[6, 6, 0, 0]}
          maxBarSize={38}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function StationBarChart({
  data,
  currency,
}: {
  data: { name: string; revenue: number }[]
  currency: string
}) {
  const height = Math.max(220, data.length * 38)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
      >
        <defs>
          <linearGradient id="stationGradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="hsl(262, 83%, 58%)" />
            <stop offset="100%" stopColor="hsl(199, 89%, 48%)" />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
        <XAxis
          type="number"
          tick={AXIS}
          axisLine={false}
          tickLine={false}
          tickFormatter={compact}
        />
        <YAxis
          type="category"
          dataKey="name"
          tick={AXIS}
          axisLine={false}
          tickLine={false}
          width={72}
        />
        <Tooltip
          content={<ChartTooltip currency={currency} />}
          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
        />
        <Bar
          dataKey="revenue"
          name="Выручка"
          fill="url(#stationGradient)"
          radius={[0, 6, 6, 0]}
          maxBarSize={26}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function TariffDonut({
  data,
  currency,
}: {
  data: { name: string; revenue: number }[]
  currency: string
}) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Tooltip content={<ChartTooltip currency={currency} />} />
        <Pie
          data={data}
          dataKey="revenue"
          nameKey="name"
          innerRadius={62}
          outerRadius={100}
          paddingAngle={3}
          stroke="none"
        >
          {data.map((_, i) => (
            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
          ))}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  )
}
