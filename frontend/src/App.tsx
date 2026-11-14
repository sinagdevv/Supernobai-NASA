import { MotionConfig } from 'motion/react'
import { Suspense, useEffect, useState } from 'react'
import { AppShell } from './components/AppShell'
import { Intro } from './components/Intro'
import { useRoute, type Screen } from './lib/router'
import { MarsUnavailable } from './components/PlanetNotice'
import { MarsCompare, MarsDossier } from './pages/app/MarsPages'
import { Analogs, Compare, Dossier, Windows } from './lib/screens'
import { BackendProvider } from './lib/api/backend'
import { LiveTerrainProvider } from './lib/api/liveContext'
import { PlanetProvider, usePlanet } from './lib/planet'
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

/** Workspace screens for the selected planet. Mars has no processing behind it, so lunar-only screens say so instead of showing lunar results under a Mars label. */
function Screens({ screen }: { screen: Screen }) {
  const { planet } = usePlanet()
  const mars = planet === 'mars'
  return (
    <>
      {screen === 'mission' && <Mission />}
      {screen === 'analogs' && <Analogs />}
      {screen === 'windows' && (mars ? <MarsUnavailable screen="windows" /> : <Windows />)}
      {screen === 'compare' && (mars ? <MarsCompare /> : <Compare />)}
      {screen === 'dossier' && (mars ? <MarsDossier /> : <Dossier />)}
    </>
  )
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
      <LiveTerrainProvider>
      <PlanetProvider>
      <AppProvider>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:rounded-md focus:bg-amber focus:px-3 focus:py-2 focus:text-ink-900">Skip to content</a>
        {route.page === 'home' ? (
          <Landing introPlayed={introPlayed} heroIn={heroIn} introDone={!intro} />
        ) : (
          <AppShell screen={route.screen}>
            {/* Tabs switch instantly: chunks are prefetched, so there is no fade and no loading state to wait through. */}
            <Suspense fallback={null}>
              <Screens screen={route.screen} />
            </Suspense>
          </AppShell>
        )}
        {intro && route.page === 'home' && <Intro onDock={() => setHeroIn(true)} onDone={done} />}
      </AppProvider>
      </PlanetProvider>
      </LiveTerrainProvider>
      </BackendProvider>
    </MotionConfig>
  )
}
