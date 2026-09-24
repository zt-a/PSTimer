import { create } from 'zustand'
import type { DashboardResponse } from '@/types'

interface DashboardState {
  dashboard: DashboardResponse | null
  connected: boolean
  lastError: string | null
  setDashboard: (d: DashboardResponse) => void
  setConnected: (c: boolean) => void
  setError: (e: string | null) => void
}

export const useDashboardStore = create<DashboardState>((set) => ({
  dashboard: null,
  connected: false,
  lastError: null,
  setDashboard: (d) => set({ dashboard: d }),
  setConnected: (c) => set({ connected: c }),
  setError: (e) => set({ lastError: e }),
}))
