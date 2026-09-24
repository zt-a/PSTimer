import { useEffect } from 'react'
import { subscribeDashboard } from '@/lib/dashboardSocket'

/**
 * Subscribes the component to the shared /ws/dashboard connection.
 * Multiple callers share a single socket (see lib/dashboardSocket.ts).
 */
export function useDashboardSocket() {
  useEffect(() => subscribeDashboard(), [])
}
