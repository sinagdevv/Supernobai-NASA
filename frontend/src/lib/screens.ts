import { lazy } from 'react'
import type { Screen } from './router'

/** Lazy screens with an explicit prefetch, so switching tabs never waits on a chunk. */
const loaders: Record<Exclude<Screen, 'mission'>, () => Promise<{ default: React.ComponentType }>> = {
  analogs: () => import('../pages/app/Analogs'),
  windows: () => import('../pages/app/Windows'),
  compare: () => import('../pages/app/Compare'),
  dossier: () => import('../pages/app/Dossier'),
}

export const Analogs = lazy(loaders.analogs)
export const Windows = lazy(loaders.windows)
export const Compare = lazy(loaders.compare)
export const Dossier = lazy(loaders.dossier)

export function prefetch(screen: Screen): Promise<unknown> {
  return screen === 'mission' ? Promise.resolve() : loaders[screen]().catch(() => undefined)
}

/** Warm every screen once the browser is idle after the first paint. */
export function prefetchAll() {
  const run = () => (['analogs', 'windows', 'compare', 'dossier'] as const).forEach((s) => void prefetch(s))
  const w = window as Window & { requestIdleCallback?: (cb: () => void) => number }
  if (w.requestIdleCallback) w.requestIdleCallback(run)
  else setTimeout(run, 1500)
}
