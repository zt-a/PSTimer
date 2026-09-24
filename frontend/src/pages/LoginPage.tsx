import { useState } from 'react'
import { motion } from 'framer-motion'
import { Gamepad2, KeyRound, Loader2, ShieldCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'

export default function LoginPage() {
  const navigate = useNavigate()
  const setToken = useAuthStore((s) => s.setToken)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await api.login(username, password)
      setToken(res.access_token, res.admin.username)
      navigate('/admin')
    } catch (err: any) {
      setError(err.message || 'Ошибка входа')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-4">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-b from-background to-black" />
        <div className="absolute -top-32 left-1/4 h-96 w-96 rounded-full bg-accent/15 blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 h-80 w-80 rounded-full bg-primary/10 blur-[100px]" />
      </div>

      <motion.form
        onSubmit={submit}
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 120, damping: 16 }}
        className="relative w-full max-w-sm rounded-2xl border border-white/10 bg-card/60 p-8 backdrop-blur-2xl"
      >
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/15 border border-accent/30">
            <Gamepad2 className="h-7 w-7 text-accent" />
          </div>
          <h1 className="text-xl font-bold text-white">Администрация</h1>
          <p className="mt-1 text-sm text-white/40">Вход в панель управления клубом</p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
            {error}
          </div>
        )}

        <label className="mb-4 block">
          <span className="mb-1.5 block text-xs font-medium text-white/50">Логин</span>
          <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 focus-within:border-accent/50">
            <ShieldCheck className="h-4 w-4 text-white/30" />
            <input
              className="w-full bg-transparent py-2.5 text-sm text-white outline-none placeholder:text-white/25"
              placeholder="admin"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              required
            />
          </div>
        </label>

        <label className="mb-6 block">
          <span className="mb-1.5 block text-xs font-medium text-white/50">Пароль</span>
          <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 focus-within:border-accent/50">
            <KeyRound className="h-4 w-4 text-white/30" />
            <input
              type="password"
              className="w-full bg-transparent py-2.5 text-sm text-white outline-none placeholder:text-white/25"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
        </label>

        <button
          type="submit"
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent py-3 text-sm font-semibold text-white transition-colors hover:bg-accent/90 disabled:opacity-60"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
          Войти
        </button>

        <a
          href="/"
          className="mt-6 block text-center text-xs text-white/30 transition-colors hover:text-white/60"
        >
          ← На экран клуба
        </a>
      </motion.form>
    </div>
  )
}
