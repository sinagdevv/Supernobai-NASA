import { useEffect, useState } from 'react'

export type Screen = 'mission' | 'analogs' | 'windows' | 'compare' | 'dossier'
export const SCREENS: Screen[] = ['mission', 'analogs', 'windows', 'compare', 'dossier']

export type Route = { page: 'home' } | { page: 'app'; screen: Screen }

function parse(hash: string): Route {
  const m = hash.match(/^#\/app\/(\w+)/)
  if (m && (SCREENS as string[]).includes(m[1])) return { page: 'app', screen: m[1] as Screen }
  return { page: 'home' }
}

export const href = (r: Route) => (r.page === 'home' ? '#/' : `#/app/${r.screen}`)
export const go = (r: Route) => {
  window.location.hash = href(r)
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash))
  useEffect(() => {
    const on = () => {
      const next = parse(window.location.hash)
      // Same route (a synthetic and a real hashchange can both arrive): keep the state object so nothing re-renders.
      setRoute((prev) => (prev.page === next.page && (prev.page === 'home' || (next.page === 'app' && prev.screen === next.screen)) ? prev : next))
      // In-page anchors on the landing page use ids; only reset scroll when entering a screen.
      if (/^#\/(app\/\w+)?$/.test(window.location.hash) || window.location.hash === '') window.scrollTo({ top: 0, behavior: 'instant' })
    }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}
