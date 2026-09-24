import type {
  AnalyticsQuery,
  Bucket,
  ClubSettings,
  DailyReport,
  DashboardResponse,
  HeatmapCell,
  PaymentPage,
  PeriodSummary,
  RevenueSeries,
  Session,
  SessionHistoryItem,
  SessionHistoryPage,
  Station,
  StationStat,
  Tariff,
  TariffStat,
  TokenResponse,
} from '@/types'

const BASE = import.meta.env.VITE_API_URL || '/api'

const TOKEN_KEY = 'pstimer_token'

// Always read the token from localStorage so that every part of the app
// (api client, zustand auth store, etc.) stays in sync.
export function setToken(t: string | null) {
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string>),
  }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`${BASE}${path}`, { ...init, headers })

  // A 401 on any endpoint other than the login call means the session is
  // gone (expired token / backend restarted). Clear it and bounce to login —
  // but only if we actually had a token, so public pages (TV dashboard) are
  // never redirected to /login for anonymous requests.
  if (res.status === 401 && !path.startsWith('/auth/login')) {
    const hadToken = !!getToken()
    setToken(null)
    if (hadToken) window.dispatchEvent(new Event('auth:logout'))
    throw new Error('Сессия истекла — войдите заново')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  // Auth
  login: (username: string, password: string) =>
    request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  // Dashboard (public)
  getDashboard: () => request<DashboardResponse>('/dashboard'),

  // Stations
  getStations: () => request<Station[]>('/stations'),
  createStation: (data: { name: string; number: number; type: string; is_active: boolean }) =>
    request<Station>('/stations', { method: 'POST', body: JSON.stringify(data) }),
  updateStation: (id: number, data: Partial<Station>) =>
    request<Station>(`/stations/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteStation: (id: number) => request<void>(`/stations/${id}`, { method: 'DELETE' }),

  // Tariffs
  getTariffs: () => request<Tariff[]>('/tariffs'),
  createTariff: (data: Omit<Tariff, 'id'>) =>
    request<Tariff>('/tariffs', { method: 'POST', body: JSON.stringify(data) }),
  updateTariff: (id: number, data: Partial<Tariff>) =>
    request<Tariff>(`/tariffs/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteTariff: (id: number) => request<void>(`/tariffs/${id}`, { method: 'DELETE' }),

  // Sessions
  startSession: (data: {
    station_id: number
    tariff_id: number
    is_open?: boolean
    duration_minutes?: number
  }) => request<Session>('/sessions', { method: 'POST', body: JSON.stringify(data) }),
  extendSession: (id: number, duration_minutes: number) =>
    request<Session>(`/sessions/${id}/extend`, { method: 'POST', body: JSON.stringify({ duration_minutes }) }),
  pauseSession: (id: number) => request<Session>(`/sessions/${id}/pause`, { method: 'POST' }),
  resumeSession: (id: number) => request<Session>(`/sessions/${id}/resume`, { method: 'POST' }),
  stopSession: (id: number) => request<Session>(`/sessions/${id}/stop`, { method: 'POST' }),
  markWarnings: (id: number, flags: { warning_5_sent?: boolean; warning_3_sent?: boolean; warning_1_sent?: boolean; expired_sent?: boolean }) =>
    request<Session>(`/sessions/${id}/warnings`, { method: 'POST', body: JSON.stringify(flags) }),
  getActiveSessions: () => request<Session[]>('/sessions/active'),

  // Settings (admin)
  getSettings: () => request<ClubSettings>('/settings'),
  updateSettings: (data: Partial<ClubSettings>) =>
    request<ClubSettings>('/settings', { method: 'PATCH', body: JSON.stringify(data) }),

  // Reports (admin)
  getDailyReport: () => request<DailyReport>('/reports/daily'),
  getSummary: (q: AnalyticsQuery = {}) =>
    request<PeriodSummary>(`/reports/summary${query(q)}`),
  getRevenueSeries: (q: AnalyticsQuery & { bucket?: Bucket } = {}) =>
    request<RevenueSeries>(`/reports/revenue${query(q)}`),
  getStationStats: (q: AnalyticsQuery = {}) =>
    request<StationStat[]>(`/reports/stations${query(q)}`),
  getTariffStats: (q: AnalyticsQuery = {}) =>
    request<TariffStat[]>(`/reports/tariffs${query(q)}`),
  getHeatmap: (q: AnalyticsQuery = {}) =>
    request<HeatmapCell[]>(`/reports/heatmap${query(q)}`),
  getSessionHistory: (
    q: AnalyticsQuery & { station_id?: number; status?: string; page?: number; page_size?: number } = {},
  ) => request<SessionHistoryPage>(`/reports/sessions${query(q)}`),
  getReceipt: (id: number) => request<SessionHistoryItem>(`/reports/sessions/${id}`),
  getPayments: (q: AnalyticsQuery & { page?: number; page_size?: number } = {}) =>
    request<PaymentPage>(`/reports/payments${query(q)}`),
  runCleanup: (retention_days?: number) =>
    request<{ deleted_sessions: number; deleted_transactions: number }>(
      `/reports/cleanup${retention_days ? `?retention_days=${retention_days}` : ''}`,
      { method: 'POST' },
    ),
}

function query(params: object): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value))
    }
  }
  const s = search.toString()
  return s ? `?${s}` : ''
}

