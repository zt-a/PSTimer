import { useEffect, useState } from 'react'
import { Save, Volume2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'
import type { ClubSettings } from '@/types'

interface Props {
  settings: ClubSettings | null
  onDone: (message: string) => void
}

export function SettingsPanel({ settings, onDone }: Props) {
  const [form, setForm] = useState<ClubSettings | null>(settings)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (settings) setForm(settings)
  }, [settings])

  if (!form) return null

  const update = (patch: Partial<ClubSettings>) =>
    setForm((f) => (f ? { ...f, ...patch } : f))

  const save = async () => {
    setLoading(true)
    try {
      await api.updateSettings({
        club_name: form.club_name,
        currency: form.currency,
        voice_enabled: form.voice_enabled,
        warning_5_enabled: form.warning_5_enabled,
        warning_3_enabled: form.warning_3_enabled,
        warning_1_enabled: form.warning_1_enabled,
        expired_enabled: form.expired_enabled,
      })
      onDone('Настройки сохранены')
    } catch (err: any) {
      onDone(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3">
        <label className="col-span-2 block">
          <span className="mb-1.5 block text-xs font-medium text-white/50">Название клуба</span>
          <input
            value={form.club_name}
            onChange={(e) => update({ club_name: e.target.value })}
            className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white outline-none focus:border-accent/50"
          />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-white/50">Валюта</span>
          <input
            value={form.currency}
            onChange={(e) => update({ currency: e.target.value })}
            className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white outline-none focus:border-accent/50"
          />
        </label>
      </div>

      <div>
        <div className="mb-3 flex items-center gap-2">
          <Volume2 className="h-4 w-4 text-white/50" />
          <span className="text-sm font-semibold text-white">Голосовые уведомления</span>
        </div>
        <div className="space-y-2">
          {[
            ['voice_enabled', 'Включить голосовые уведомления'],
            ['warning_5_enabled', 'Предупреждение за 5 минут'],
            ['warning_3_enabled', 'Предупреждение за 3 минуты'],
            ['warning_1_enabled', 'Предупреждение за 1 минуту'],
            ['expired_enabled', 'Время закончилось'],
          ].map(([key, label]) => (
            <label
              key={key}
              className="flex items-center justify-between rounded-xl border border-white/10 bg-white/5 px-4 py-3"
            >
              <span className="text-sm text-white/70">{label}</span>
              <input
                type="checkbox"
                checked={(form as any)[key] as boolean}
                onChange={(e) => update({ [key]: e.target.checked } as any)}
                className="h-4 w-4 rounded accent-accent"
              />
            </label>
          ))}
        </div>
      </div>

      <Button className="w-full" onClick={save} disabled={loading}>
        <Save className="h-4 w-4" />
        {loading ? '…' : 'Сохранить настройки'}
      </Button>
    </div>
  )
}
