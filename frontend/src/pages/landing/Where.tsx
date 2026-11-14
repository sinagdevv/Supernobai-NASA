import { motion, useMotionValue, useReducedMotion, useScroll, useTransform, type MotionValue } from 'motion/react'
import { useMemo, useRef, useState, memo } from 'react'
import { StatusBadge, StatusGlyph, cx } from '../../components/ui'
import { ProfileThumb } from '../../components/viz'
import { ChapterText, Plate, useBox, useMedia } from '../../components/landing/kit'
import { DEFAULT_MISSION } from '../../data/mission'
import { SITES, shortName } from '../../data/sites'
import { BASEMAP_CREDITS } from '../../data/sources'
import type { Site } from '../../data/types'
import { regionById } from '../../lib/assess'
import { enterWorkspace } from '../../lib/transition'
import { useApp } from '../../lib/store'

/*
 * Chapter 01 · WHERE. Real satellite imagery (the Explorer's own Esri source) behind the example sites.
 * Scrolling pushes the camera in slowly and reveals the candidates one by one, each with the status the Explorer would give it.
 * The Antarctic example is left out only so the crop can be tight on the other seven; it is in the workspace.
 */

const TILE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile'
const FEATURED = 'craters-of-the-moon'
const SHOWN = SITES.filter((s) => s.id !== 'dry-valleys')

const wx = (lon: number) => (lon + 180) / 360
const wy = (lat: number) => { const s = Math.sin((lat * Math.PI) / 180); return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI) }

const BBOX = (() => {
  const xs = SHOWN.map((s) => wx(s.lon)), ys = SHOWN.map((s) => wy(s.lat))
  return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) }
})()

/** Where the world sits in a w×h window so the example sites fill it with a margin. */
function frame(w: number, h: number) {
  const bw = BBOX.x1 - BBOX.x0, bh = BBOX.y1 - BBOX.y0
  const S = Math.max(w, h, Math.min((w * 0.8) / bw, (h * 0.66) / bh)) // world square side in px
  const cl = (v: number, extent: number) => Math.min(0, Math.max(extent - S, v)) // keep every edge of the world outside the window
  const left = cl(w / 2 - ((BBOX.x0 + BBOX.x1) / 2) * S, w), top = cl(h / 2 - ((BBOX.y0 + BBOX.y1) / 2) * S, h)
  const z = Math.max(1, Math.min(5, Math.ceil(Math.log2(S / 256))))
  const f = SHOWN.find((x) => x.id === FEATURED)!
  return { S, left, top, z, w, h, ox: left + wx(f.lon) * S, oy: top + wy(f.lat) * S }
}
type Frame = ReturnType<typeof frame>

function Tiles({ F }: { F: Frame }) {
  const { S, left, top, z, w, h } = F
  const n = 2 ** z, t = S / n
  const tiles = useMemo(() => {
    const out: { x: number; y: number }[] = []
    const lo = (o: number) => Math.max(0, Math.floor((-o / S) * n))
    const hi = (a: number, o: number) => Math.min(n - 1, Math.floor(((a - o) / S) * n))
    for (let y = lo(top); y <= hi(h, top); y++) for (let x = lo(left); x <= hi(w, left); x++) out.push({ x, y })
    return out
  }, [S, n, w, h, left, top])
  return (
    <div aria-hidden className="absolute inset-0" style={{ filter: 'brightness(0.58) saturate(0.72) contrast(1.06)' }}>
      {tiles.map(({ x, y }) => (
        // One pixel of overlap per tile hides sub-pixel seams.
        <img key={`${x}/${y}`} src={`${TILE}/${z}/${y}/${x}`} alt="" loading="lazy" decoding="async" draggable={false} className="absolute max-w-none select-none"
          style={{ left: left + x * t, top: top + y * t, width: t + 1, height: t + 1 }} />
      ))}
    </div>
  )
}

function Pin({ site, F, s, p, i, active, touch, onActive, onOpen, status, reduce }: { site: Site; F: Frame; touch: boolean; s: MotionValue<number>; p: MotionValue<number>; i: number; active: boolean; onActive: (id: string | null) => void; onOpen: (id: string) => void; status: 'potential' | 'not-suitable' | 'not-assessed'; reduce: boolean }) {
  const px = F.left + wx(site.lon) * F.S, py = F.top + wy(site.lat) * F.S
  const x = useTransform(s, (v) => F.ox + (px - F.ox) * v)
  const y = useTransform(s, (v) => F.oy + (py - F.oy) * v)
  const t0 = 0.06 + i * 0.07
  const op = useTransform(p, [t0, t0 + 0.09], [0, 1])
  const sc = useTransform(p, [t0, t0 + 0.09], [0.7, 1])
  const flip = px > F.w * 0.62
  return (
    <motion.div className="absolute top-0 left-0" style={{ x, y, zIndex: active ? 20 : 10 }}>
      <motion.div style={reduce ? undefined : { opacity: op, scale: sc }} className="absolute -translate-x-1/2 -translate-y-1/2">
        <button type="button" aria-label={`${site.name}, ${site.place}. ${status === 'potential' ? 'Potentially suitable' : status === 'not-suitable' ? 'Not suitable' : 'Not yet assessed'}. Open in the Analog Explorer.`}
          onPointerEnter={(e) => e.pointerType === 'mouse' && onActive(site.id)} onPointerLeave={(e) => e.pointerType === 'mouse' && onActive(null)} onFocus={() => !touch && onActive(site.id)} onBlur={() => !touch && onActive(null)}
          onClick={() => (touch && !active ? onActive(site.id) : onOpen(site.id))} /* touch: the first tap shows the site, the second opens it */ className="group relative grid h-11 w-11 place-items-center rounded-full">
          <span className={cx('relative grid h-[26px] w-[26px] place-items-center rounded-full border-2 bg-ink-900/90 shadow-[0_2px_8px_rgb(0_0_0/0.6)] transition-transform duration-[var(--duration-fast)] ease-[var(--ease-out)] group-active:scale-95', active ? 'scale-110 border-amber ring-2 ring-amber/40 ring-offset-2 ring-offset-ink-900' : 'border-[var(--line-strong)]')}>
            <StatusGlyph status={status} size={16} />
          </span>
        </button>
        <div aria-hidden className={cx('glass pointer-events-none absolute top-1/2 w-[212px] -translate-y-1/2 rounded-[var(--radius-md)] border border-amber/45 p-2.5 shadow-[var(--shadow-pop)] transition-[opacity,transform] duration-[var(--duration-fast)] ease-[var(--ease-out)]', flip ? 'right-[calc(50%+22px)] origin-right' : 'left-[calc(50%+22px)] origin-left', active ? 'scale-100 opacity-100' : 'scale-[0.97] opacity-0')}>
          <p className="text-[14px] leading-tight font-medium text-paper">{shortName(site)}</p>
          <p className="mt-0.5 text-[13px] text-silver-400">{site.place}</p>
          <ProfileThumb seed={site.seed} w={188} h={34} className="mt-2 block h-[34px] w-full" />
          <div className="mt-2"><StatusBadge status={status} compact /></div>
        </div>
      </motion.div>
    </motion.div>
  )
}

function Where() {
  const reduce = !!useReducedMotion()
  const { assessments } = useApp()
  const region = regionById(DEFAULT_MISSION.regionId)
  const [plateRef, box] = useBox<HTMLDivElement>()
  const wrap = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: wrap, offset: ['start 85%', 'end 40%'] })
  const still = useMotionValue(1)
  const p = reduce ? still : scrollYProgress
  const s = useTransform(p, [0, 1], reduce ? [1, 1] : [1, 1.22])
  const [hov, setHov] = useState<string | null>(null)
  const act = hov ?? FEATURED
  const { select } = useApp()
  const touch = useMedia('(hover: none)')
  const F = useMemo(() => (box.w ? frame(box.w, box.h) : null), [box.w, box.h])
  const open = (id: string) => { select(id); enterWorkspace('analogs') }

  return (
    <section ref={wrap} id="where" aria-labelledby="where-title" className="scroll-mt-14 border-t border-[var(--line)] py-16 md:py-24">
      <div className="mx-auto grid max-w-[1680px] gap-x-12 gap-y-8 px-4 *:min-w-0 md:px-8 lg:grid-cols-12 lg:items-center">
        <div className="lg:col-span-4">
          <ChapterText id="where-title" n="01" q="Where to test" title="Find ground that resembles the problem.">
            Screen Earth sites against your rover’s slope and roughness limits, at a scale the elevation data can resolve.
          </ChapterText>
        </div>
        <div className="lg:col-span-8">
          <Plate label="A satellite map of example Earth analog sites, each marked with its assessment status" foot={<>Example sites; statuses come from the prototype’s illustrative data. Select a site to open the Explorer.</>}>
            <div ref={plateRef} className="relative aspect-[8/5] min-h-[340px] w-full overflow-hidden">
              {F && (
                <>
                  <motion.div className="absolute inset-0" style={{ scale: s, transformOrigin: `${F.ox}px ${F.oy}px` }}>
                    <Tiles F={F} />
                  </motion.div>
                  <div aria-hidden className="pointer-events-none absolute inset-0" style={{ background: 'linear-gradient(180deg, rgb(12 15 19 / 0.5), rgb(12 15 19 / 0) 38%, rgb(12 15 19 / 0.55))' }} />
                  {SHOWN.map((site, i) => (
                    <Pin key={site.id} site={site} F={F} s={s} p={p} i={i} reduce={reduce} touch={touch} active={act === site.id} onActive={setHov} onOpen={open} status={assessments.get(site.id)!.overall} />
                  ))}
                  <div className="glass absolute top-3 left-3 flex items-center gap-3 rounded-[var(--radius-md)] border border-[var(--line-strong)] py-2 pr-3.5 pl-2.5">
                    <ProfileThumb kind="moon" seed={region.seed} w={72} h={30} className="hidden h-[30px] w-[72px] shrink-0 min-[400px]:block" />
                    <div className="leading-tight">
                      <p className="text-[13px] font-medium text-paper">Lunar reference</p>
                      <p className="mono mt-0.5 text-[12px] text-silver-300">Slope ≤ {DEFAULT_MISSION.slopeMax}° · Sun {DEFAULT_MISSION.elMin}–{DEFAULT_MISSION.elMax}°</p>
                    </div>
                  </div>
                  <p className="glass absolute right-3 bottom-3 max-w-[70%] rounded-[var(--radius-sm)] px-2 py-1 text-[12px] leading-snug text-silver-300">{BASEMAP_CREDITS[0]}</p>
                </>
              )}
            </div>
          </Plate>
        </div>
      </div>
    </section>
  )
}

export default memo(Where)
