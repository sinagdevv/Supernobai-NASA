import { flushSync } from 'react-dom'
import type { Screen } from './router'
import { prefetch } from './screens'

type VT = (cb: () => void) => unknown

/**
 * Landing to workspace. Where the browser supports View Transitions the page cross-fades briefly and the lockup (`.vt-lockup`)
 * stays put as a shared element; elsewhere, and under reduced motion, it is an ordinary instant navigation.
 * Never used between workspace tabs: those switch with no transition at all.
 *
 * Only the Mission screen uses it. A transition freezes rendering until its update callback returns, so a destination that does real work
 * on first render (the Explorer builds a WebGL map) would hold the page still; those navigate instantly instead.
 *
 * Two constraints shape this: rendering (and so requestAnimationFrame) is suspended while the browser waits for the update
 * callback, so the DOM must change synchronously inside it (flushSync); and the screen's code must already be loaded, or the
 * transition would capture a blank Suspense fallback. The wait for the chunk is capped, and zero when it is already cached.
 */
export async function enterWorkspace(screen: Screen) {
  const target = `#/app/${screen}`
  await Promise.race([prefetch(screen), new Promise((r) => setTimeout(r, 1500))])
  const start = (document as Document & { startViewTransition?: VT }).startViewTransition
  if (!start || screen !== 'mission' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    window.location.hash = target
    return
  }
  start.call(document, () => {
    flushSync(() => {
      window.location.hash = target
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
  })
}
