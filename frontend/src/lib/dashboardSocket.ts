import { useDashboardStore } from '@/stores/dashboard'
import type { DashboardResponse } from '@/types'

/**
 * Single shared WebSocket to /ws/dashboard.
 *
 * Why a singleton: several components (TV page, admin page) mount the same
 * hook, and React StrictMode double-mounts effects in dev. Without sharing,
 * every mount opened its own socket, closing one flipped the global
 * `connected` flag to false and flashed the "connection lost" banner.
 *
 * The banner is now only shown after the socket has been down for a grace
 * period, so a short blip or an initial connect never triggers it.
 */

const WS_URL =
  import.meta.env.VITE_WS_URL ||
  (() => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${location.host}/ws/dashboard`
  })()

const RECONNECT_MIN = 500
const RECONNECT_MAX = 10_000
const GRACE_MS = 4_000
const PING_MS = 20_000

let socket: WebSocket | null = null
let refCount = 0
let retry = 0
let reconnectTimer: number | undefined
let pingTimer: number | undefined
let graceTimer: number | undefined
let manuallyClosed = false

function setConnected(v: boolean) {
  useDashboardStore.getState().setConnected(v)
}

function setError(e: string | null) {
  useDashboardStore.getState().setError(e)
}

function scheduleReconnect() {
  if (reconnectTimer) return
  const delay = Math.min(RECONNECT_MIN * 2 ** retry, RECONNECT_MAX)
  retry += 1
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = undefined
    open()
  }, delay)
}

function open() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return
  }
  manuallyClosed = false
  socket = new WebSocket(WS_URL)

  socket.onopen = () => {
    retry = 0
    if (graceTimer) {
      clearTimeout(graceTimer)
      graceTimer = undefined
    }
    setConnected(true)
    setError(null)
    // keepalive so proxies don't drop idle connections
    if (pingTimer) clearInterval(pingTimer)
    pingTimer = window.setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) socket.send('ping')
    }, PING_MS)
  }

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'dashboard' && data.payload) {
        useDashboardStore.getState().setDashboard(data.payload as DashboardResponse)
      }
    } catch {
      /* ignore malformed frames */
    }
  }

  socket.onclose = () => {
    if (pingTimer) {
      clearInterval(pingTimer)
      pingTimer = undefined
    }
    if (manuallyClosed) return

    // show the banner only if we stay down past the grace period
    if (!graceTimer) {
      graceTimer = window.setTimeout(() => {
        graceTimer = undefined
        setConnected(false)
        setError('Соединение потеряно')
      }, GRACE_MS)
    }
    scheduleReconnect()
  }

  socket.onerror = () => {
    socket?.close()
  }
}

function ensureStarted() {
  if (refCount === 0) {
    retry = 0
    open()
  }
  refCount += 1
}

function release() {
  refCount -= 1
  if (refCount > 0) return
  // delay teardown one tick so StrictMode's remount reuses the socket
  window.setTimeout(() => {
    if (refCount > 0) return
    manuallyClosed = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = undefined
    }
    if (pingTimer) {
      clearInterval(pingTimer)
      pingTimer = undefined
    }
    if (graceTimer) {
      clearTimeout(graceTimer)
      graceTimer = undefined
    }
    socket?.close()
    socket = null
  }, 0)
}

/** Subscribe to the shared dashboard socket. Returns an unsubscribe fn. */
export function subscribeDashboard(): () => void {
  ensureStarted()
  return release
}
