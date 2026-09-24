import { create } from 'zustand'
import { setToken as persistToken } from '@/lib/api'

interface AuthState {
  token: string | null
  username: string | null
  setToken: (token: string, username: string) => void
  logout: () => void
  isAuthenticated: () => boolean
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('pstimer_token'),
  username: localStorage.getItem('pstimer_username'),
  setToken: (token, username) => {
    persistToken(token)
    localStorage.setItem('pstimer_username', username)
    set({ token, username })
  },
  logout: () => {
    persistToken(null)
    localStorage.removeItem('pstimer_username')
    set({ token: null, username: null })
  },
  isAuthenticated: () => !!get().token,
}))
