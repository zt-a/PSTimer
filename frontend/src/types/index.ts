export type StationType = 'PS4' | 'PS5'

export type StationStatus = 'ACTIVE' | 'OPEN' | 'PAUSED' | 'EXPIRED' | 'COMPLETED' | null

export interface Admin {
  id: number
  username: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  admin: Admin
}

export interface Station {
  id: number
  name: string
  number: number
  type: StationType
  is_active: boolean
}

export interface Tariff {
  id: number
  name: string
  price_per_hour: number
  is_active: boolean
}

export interface Session {
  id: number
  station_id: number
  tariff_id: number | null
  type: 'FIXED' | 'OPEN'
  status: Exclude<StationStatus, null>
  started_at: string
  expires_at: string | null
  ended_at: string | null
  paused_at: string | null
  total_paused_seconds: number
  price_snapshot: number
  amount: number | null
  warning_5_sent: boolean
  warning_3_sent: boolean
  warning_1_sent: boolean
  expired_sent: boolean
}

export interface StationState {
  id: number
  name: string
  number: number
  type: StationType
  is_active: boolean
  status: StationStatus
  session_id: number | null
  session_type: 'FIXED' | 'OPEN' | null
  started_at: string | null
  expires_at: string | null
  paused_at: string | null
  total_paused_seconds: number
  price_snapshot: number | null
  amount: number | null
  server_time: string
  warning_5_sent: boolean
  warning_3_sent: boolean
  warning_1_sent: boolean
  expired_sent: boolean
}

export interface DashboardResponse {
  club_name: string
  currency: string
  voice_enabled: boolean
  server_time: string
  stations: StationState[]
}

export type ClubSettings = {
  id: number
  club_name: string
  currency: string
  voice_enabled: boolean
  warning_5_enabled: boolean
  warning_3_enabled: boolean
  warning_1_enabled: boolean
  expired_enabled: boolean
}

export interface ReportLine {
  time: string
  station: string
  session_id: number
  duration_minutes: number
  tariff_name: string
  amount: number
  status: string
}

export interface DailyReport {
  date: string
  total_revenue: number
  completed_sessions: number
  total_play_seconds: number
  num_transactions: number
  lines: ReportLine[]
}

// ── Analytics ────────────────────────────────────────────────────────────────
export type PeriodKey = 'today' | 'week' | 'month' | 'year' | 'custom'
export type Bucket = 'hour' | 'day' | 'week' | 'month'

export interface PeriodSummary {
  date_from: string
  date_to: string
  revenue: number
  sessions: number
  transactions: number
  avg_check: number
  play_seconds: number
  utilization: number
  revenue_delta: number | null
  sessions_delta: number | null
  avg_check_delta: number | null
  play_seconds_delta: number | null
}

export interface SeriesPoint {
  label: string
  start: string
  revenue: number
  sessions: number
  play_seconds: number
}

export interface RevenueSeries {
  bucket: Bucket
  points: SeriesPoint[]
}

export interface StationStat {
  station_id: number
  name: string
  number: number
  revenue: number
  sessions: number
  play_seconds: number
}

export interface TariffStat {
  tariff_id: number | null
  name: string
  revenue: number
  sessions: number
}

export interface HeatmapCell {
  weekday: number
  hour: number
  revenue: number
  sessions: number
}

export interface SessionHistoryItem {
  id: number
  station_id: number
  station_name: string
  station_number: number
  tariff_name: string
  type: 'FIXED' | 'OPEN'
  status: Exclude<StationStatus, null>
  started_at: string
  ended_at: string | null
  duration_minutes: number
  total_paused_seconds: number
  price_snapshot: number
  amount: number | null
}

export interface SessionHistoryPage {
  total: number
  page: number
  page_size: number
  items: SessionHistoryItem[]
}

export interface PaymentItem {
  id: number
  created_at: string
  session_id: number
  station_name: string
  tariff_name: string
  amount: number
  payment_type: string
}

export interface PaymentPage {
  total: number
  total_amount: number
  page: number
  page_size: number
  items: PaymentItem[]
}

export interface AnalyticsQuery {
  period?: PeriodKey
  date_from?: string
  date_to?: string
}
