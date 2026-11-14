import { MotionConfig } from 'motion/react'
import { Suspense, useEffect, useState } from 'react'
import { AppShell } from './components/AppShell'
import { Intro } from './components/Intro'
import { useRoute } from './lib/router'
import { Analogs, Compare, Dossier, Windows } from './lib/screens'
import { BackendProvider } from './lib/api/backend'
import { AppProvider } from './lib/store'
import Landing from './pages/Landing'
import Mission from './pages/app/Mission'

const SEEN = 'tw-intro-seen'
const shouldIntro = () => {
  try {
    return !sessionStorage.getItem(SEEN) && !/^#\/app\//.test(window.location.hash)
  } catch {
    return false
  }
}

export default function App() {
  const route = useRoute()
  const [intro, setIntro] = useState(shouldIntro)
  const [introPlayed] = useState(intro)
  const [heroIn, setHeroIn] = useState(false)
  // The first-paint background from index.html has done its job once React is running.
  useEffect(() => { document.getElementById('boot-bg')?.remove() }, [])
  const done = () => {
    try { sessionStorage.setItem(SEEN, '1') } catch { /* private mode: intro may replay next load */ }
    setIntro(false)
  }

  return (
    <MotionConfig reducedMotion="user">
      <BackendProvider>
      <AppProvider>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:rounded-md focus:bg-amber focus:px-3 focus:py-2 focus:text-ink-900">Skip to content</a>
        {route.page === 'home' ? (
          <Landing introPlayed={introPlayed} heroIn={heroIn} introDone={!intro} />
        ) : (
          <AppShell screen={route.screen}>
            {/* Tabs switch instantly: chunks are prefetched, so there is no fade and no loading state to wait through. */}
            <Suspense fallback={null}>
              {route.screen === 'mission' && <Mission />}
              {route.screen === 'analogs' && <Analogs />}
              {route.screen === 'windows' && <Windows />}
              {route.screen === 'compare' && <Compare />}
              {route.screen === 'dossier' && <Dossier />}
            </Suspense>
          </AppShell>
        )}
        {intro && route.page === 'home' && <Intro onDock={() => setHeroIn(true)} onDone={done} />}
      </AppProvider>
      </BackendProvider>
    </MotionConfig>
  )
}
