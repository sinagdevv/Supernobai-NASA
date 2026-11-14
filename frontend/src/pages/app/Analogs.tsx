import { AnimatePresence, animate, motion, useMotionValue, useReducedMotion } from 'motion/react'
import { ChevronUp } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { EarthMap } from '../../components/map/EarthMap'
import { FilterDrawer } from '../../components/map/FilterPanel'
import { SiteDetail } from '../../components/map/SiteDetail'
import { SiteList } from '../../components/map/SiteList'
import { activeFilterCount, useMedia } from '../../components/map/shared'
import { cx, StatusGlyph } from '../../components/ui'
import { SITES, siteById } from '../../data/sites'
import { LiveChip, LivePanel, PatchCard } from '../../components/map/LivePanel'
import { useLive } from '../../lib/api/liveContext'
import { useApp } from '../../lib/store'

const PEEK = 88
const SPRING = { type: 'spring', bounce: 0, duration: 0.35 } as const

/** Progressive resistance past a limit (Apple's rubber-band). */
const rubber = (over: number, dim: number) => (over * dim * 0.55) / (dim + 0.55 * over)
/** Where a release velocity (px/s) would coast to — exponential decay, decelerationRate 0.998. */
const project = (v: number) => ((v / 1000) * 0.998) / (1 - 0.998)

export default function Analogs() {
  const { results, selectedId, select, assessments, compareIds, baseMap, relief, filters } = useApp()
  const live = useLive()
  const isDesktop = useMedia('(min-width: 1024px)')
  const reduce = useReducedMotion()
  const [drawer, setDrawer] = useState(false)
  const [sheet, setSheet] = useState<'peek' | 'open'>('peek')
  const [hoverId, setHoverId] = useState<string | null>(null)

  const visibleIds = useMemo(() => new Set(results), [results])
  const statuses = useMemo(() => new Map([...assessments].map(([id, a]) => [id, a.overall])), [assessments])
  const selected = siteById(selectedId)
  const nFilters = activeFilterCount(filters)

  /* ── bottom sheet: y = 0 is fully open, y = peekY is the 88px peek ── */
  const sheetRef = useRef<HTMLElement>(null)
  const y = useMotionValue(9999)
  const [sheetH, setSheetH] = useState(0)
  const peekY = Math.max(0, sheetH - PEEK)
  const suppressClick = useRef(false) // a drag that ends on the handle must not also toggle
  const drag = useRef<{ startY: number; startVal: number; moved: boolean; samples: { t: number; y: number }[] } | null>(null)

  useEffect(() => {
    const el = sheetRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setSheetH(el.offsetHeight))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  // A size change re-seats the sheet without animating.
  useEffect(() => {
    if (sheetH) y.set(sheet === 'open' ? 0 : peekY)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheetH])

  const snapTo = useCallback(
    (to: 'peek' | 'open', velocity = 0) => {
      setSheet(to)
      animate(y, to === 'open' ? 0 : peekY, reduce ? { duration: 0 } : { ...SPRING, velocity })
    },
    [peekY, reduce, y],
  )

  const onDown = (e: React.PointerEvent) => {
    if (isDesktop) return
    e.currentTarget.setPointerCapture(e.pointerId)
    y.stop() // grab it mid-flight: tracking starts from the on-screen value
    drag.current = { startY: e.clientY, startVal: y.get(), moved: false, samples: [{ t: e.timeStamp, y: e.clientY }] }
  }
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current
    if (!d) return
    const dy = e.clientY - d.startY
    if (Math.abs(dy) > 6) d.moved = true
    const v = d.startVal + dy
    y.set(v < 0 ? -rubber(-v, sheetH) : v > peekY ? peekY + rubber(v - peekY, sheetH) : v)
    d.samples = [...d.samples.slice(-5), { t: e.timeStamp, y: e.clientY }]
  }
  const onUp = () => {
    const d = drag.current
    drag.current = null
    if (!d?.moved) return
    suppressClick.current = true
    window.setTimeout(() => (suppressClick.current = false), 80)
    const a = d.samples[0], b = d.samples[d.samples.length - 1]
    const v = b.t > a.t ? ((b.y - a.y) / (b.t - a.t)) * 1000 : 0
    const end = y.get() + project(v) // decide from where the flick is heading, not where it let go
    snapTo(end < peekY / 2 ? 'open' : 'peek', v)
  }
  const onToggle = () => {
    if (suppressClick.current) return
    snapTo(sheet === 'open' ? 'peek' : 'open')
  }

  const pick = useCallback(
    (id: string) => {
      select(id)
      if (!isDesktop) snapTo('open')
    },
    [select, isDesktop, snapTo],
  )

  const bottomPad = isDesktop ? 0 : sheet === 'open' ? Math.round(window.innerHeight * 0.45) : PEEK + 24
  const summary = selected ? selected.name : `${results.length} candidate site${results.length === 1 ? '' : 's'}`
  const panelHidden = !isDesktop && sheet === 'peek'

  return (
    <div
      className="relative h-[calc(100dvh-var(--topbar-h)-var(--tabbar-h))] overflow-hidden lg:grid lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[minmax(0,1fr)_360px]"
      style={{ ['--sheet-offset' as string]: isDesktop ? '0px' : `${PEEK}px` }}
    >
      <h1 className="sr-only">Earth analog explorer</h1>
      <p className="sr-only" role="status" aria-live="polite">
        {results.length} of {SITES.length} candidate sites shown.{selected ? ` Selected ${selected.name}.` : ''}
      </p>

      <FilterDrawer open={drawer} onClose={() => setDrawer(false)} />

      {/* The map is the workspace: toolbar floats on it, panels support it. */}
      <div className="absolute inset-0 min-w-0 lg:relative lg:inset-auto">
        <EarthMap selectedId={selectedId} hoverId={hoverId} compareIds={compareIds} visibleIds={visibleIds} statuses={statuses} baseMap={baseMap} relief={relief} bottomPad={bottomPad} onSelect={pick} nFilters={nFilters} onFilters={() => setDrawer(true)} live={live} livePanel={<LivePanel live={live} />} liveUi={<><LiveChip live={live} /><PatchCard live={live} /></>} />
      </div>

      {/* Results / evidence — right column at ≥1024, draggable bottom sheet below */}
      <motion.aside
        ref={sheetRef}
        aria-label="Candidate sites and evidence"
        onKeyDown={(e) => e.key === 'Escape' && !isDesktop && snapTo('peek')}
        style={isDesktop ? undefined : { y }}
        className="absolute inset-x-0 bottom-0 z-20 flex h-[62%] min-h-0 flex-col overflow-hidden rounded-t-[var(--radius-lg)] border-t border-[var(--line-strong)] bg-ink-850 shadow-[var(--shadow-pop)] lg:static lg:z-auto lg:h-auto lg:rounded-none lg:border-t-0 lg:border-l lg:border-[var(--line)] lg:shadow-none"
      >
        <button
          type="button"
          aria-expanded={sheet === 'open'}
          aria-controls="analogs-panel"
          onClick={onToggle}
          onPointerDown={onDown}
          onPointerMove={onMove}
          onPointerUp={onUp}
          onPointerCancel={onUp}
          className="flex shrink-0 flex-col items-stretch px-4 lg:hidden"
          style={{ height: PEEK, touchAction: 'none' }}
        >
          <span aria-hidden className="mx-auto mt-2 h-1 w-9 rounded-full bg-ink-500" />
          <span className="flex flex-1 items-center gap-3 text-left">
            {selected && <StatusGlyph status={assessments.get(selected.id)!.overall} size={18} />}
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[15px] font-semibold text-paper">{summary}</span>
              <span className="block text-[12px] text-silver-400">{sheet === 'open' ? 'Tap or drag down to see the map' : selected ? 'Tap or drag up for evidence' : 'Tap or drag up to browse and compare'}</span>
            </span>
            <ChevronUp size={18} aria-hidden className={cx('shrink-0 text-silver-400 transition-transform duration-[var(--duration-base)] ease-[var(--ease-out)]', sheet === 'open' && 'rotate-180')} />
          </span>
        </button>

        {/* List stays mounted underneath; the detail layer slides over it from the right and returns the same way. */}
        <div id="analogs-panel" className="relative min-h-0 flex-1 overflow-hidden" inert={panelHidden}>
          <div className="h-full" inert={!!selectedId}>
            <SiteList onHover={setHoverId} onPick={pick} onFilters={() => setDrawer(true)} />
          </div>
          <AnimatePresence initial={false}>
            {selectedId && (
              <motion.div
                key="detail"
                className="absolute inset-0 bg-ink-850"
                initial={reduce ? { opacity: 0 } : { x: '100%' }}
                animate={reduce ? { opacity: 1 } : { x: 0 }}
                exit={reduce ? { opacity: 0 } : { x: '100%' }}
                transition={{ type: 'spring', bounce: 0, duration: 0.28 }}
              >
                <SiteDetail key={selectedId} id={selectedId} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.aside>
    </div>
  )
}
