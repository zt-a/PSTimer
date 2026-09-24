import { useEffect, useState } from 'react'

/**
 * Counts down (or up) to fewer seconds. Correct for browser refresh AND
 * for server/client clock drift: units are milliseconds.
 */
export function useCountdown(target: number | null): number | null {
  const [ms, setMs] = useState(() => {
    if (target === null) return null
    const remaining = target - Date.now()
    return Math.max(0, remaining)
  })

  useEffect(() => {
    if (target === null) {
      setMs(null)
      return
    }
    const update = () => {
      const remaining = target - Date.now()
      setMs(Math.max(0, remaining))
    }
    update()
    const id = setInterval(update, 250)
    return () => clearInterval(id)
  }, [target])

  return ms
}
