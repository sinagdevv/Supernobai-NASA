import { AttributionControl, LngLatBounds, Map as MapLibreMap, Marker, ScaleControl, setWorkerUrl } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { motion } from 'motion/react'
import { X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { SITES, siteById } from '../../data/sites'
import type { Site, Status } from '../../data/types'
import { STATUS_LABEL } from '../../lib/assess'
import { EASE } from '../../lib/motion'
import type { BaseMap } from '../../lib/store'
import type { LiveTerrain } from '../../lib/api/live'
import { SchematicMap } from '../SchematicMap'
import { cx, StatusGlyph } from '../ui'

// Let Vite bundle the worker (with its shared chunk) so dev and production both resolve it.
setWorkerUrl(workerUrl)
import { MapControls } from './MapControls'
import { BASE_KEYS, baseId, buildStyle, setRelief } from './mapStyle'
import { PATCH_LAYER, fitCoords, setSelectedPatch, syncOverlay, syncScreen } from './liveLayers'

const WORLD: [[number, number], [number, number]] = [[-170, -82], [178, 74]]
const TILE_TIMEOUT_MS = 6000

interface Props {
  selectedId: string | null
  hoverId: string | null
  compareIds: string[]
  visibleIds: Set<string>
  statuses: Map<string, Status>
  baseMap: BaseMap
  relief: boolean
  /** Pixels of the viewport covered at the bottom by the mobile sheet (camera padding) */
  bottomPad: number
  onSelect: (id: string) => void
  nFilters: number
  onFilters: () => void
  /** Layer 3 results to draw (overlay, screening patches), the controls for them, and their on-map provenance. */
  live?: LiveTerrain
  livePanel?: ReactNode
  liveUi?: ReactNode
}

function SiteMarker({ site, status, selected, hover, compared, onSelect }: { site: Site; status: Status; selected: boolean; hover: boolean; compared: boolean; onSelect: (id: string) => void }) {
  return (
    <button
      type="button"
      aria-label={`${site.name}, ${site.place}. ${STATUS_LABEL[status]}${compared ? '. In comparison' : ''}`}
      aria-pressed={selected}
      onClick={() => onSelect(site.id)}
      className="group relative grid h-11 w-11 place-items-center rounded-full"
    >
      {selected && (
        <motion.span aria-hidden className="absolute h-[26px] w-[26px] rounded-full border-2 border-amber" initial={{ scale: 1, opacity: 0.95 }} animate={{ scale: 2.8, opacity: 0 }} transition={{ duration: 1.1, ease: EASE }} />
      )}
      <span
        className={cx(
          'relative grid h-[26px] w-[26px] place-items-center rounded-full border-2 bg-ink-900/90 shadow-[0_2px_8px_rgb(0_0_0/0.6)] transition-transform duration-[var(--duration-fast)] ease-[var(--ease-out)] group-hover:scale-110 group-active:scale-95',
          compared ? 'border-cyan' : 'border-[var(--line-strong)]',
          selected && 'ring-2 ring-amber ring-offset-2 ring-offset-ink-900',
          (hover || selected) && 'scale-110',
        )}
      >
        <StatusGlyph status={status} size={16} />
      </span>
      {selected && (
        <span aria-hidden className="pointer-events-none absolute top-1/2 left-[calc(50%+17px)] flex -translate-y-1/2 items-center">
          <span className="h-px w-3.5 bg-amber" />
          <span className="glass rounded-[var(--radius-sm)] border border-amber/50 px-2 py-1 text-[12px] leading-none font-medium whitespace-nowrap text-paper">{site.name}</span>
        </span>
      )}
      <span role="presentation" className={cx('pointer-events-none absolute bottom-full left-1/2 z-10 mb-0.5 -translate-x-1/2 rounded-[var(--radius-sm)] border border-[var(--line-strong)] bg-ink-900 px-2 py-1 text-[12px] font-medium whitespace-nowrap text-paper opacity-0 shadow-[var(--shadow-pop)] transition-opacity duration-[var(--duration-fast)]', !selected && 'group-hover:opacity-100 group-focus-visible:opacity-100')}>
        {site.name}
      </span>
    </button>
  )
}

export function EarthMap(props: Props) {
  const { selectedId, hoverId, compareIds, visibleIds, statuses, baseMap, relief, onSelect } = props
  const hostRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const coordRef = useRef<HTMLSpanElement>(null)
  const zoomRef = useRef<HTMLSpanElement>(null)
  const [els, setEls] = useState<Record<string, HTMLDivElement>>({})
  const [noWebGL, setNoWebGL] = useState(false)
  const [tileFail, setTileFail] = useState(false)
  const [bannerOff, setBannerOff] = useState(false)
  const health = useRef({ okBases: new Set<BaseMap>(), errors: 0, base: props.baseMap })
  const latest = useRef(props)
  useEffect(() => {
    latest.current = props
  })

  /* ── create / destroy the map (StrictMode-safe) ── */
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    let map: MapLibreMap
    try {
      map = new MapLibreMap({
        container: host,
        style: buildStyle(latest.current.baseMap),
        center: [10, 20],
        zoom: 1,
        minZoom: 0,
        maxZoom: 18,
        // One world only: repeated continents at the edge were MapLibre's default world-copy rendering.
        renderWorldCopies: false,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        fadeDuration: 200,
      })
    } catch {
      setNoWebGL(true)
      return
    }
    mapRef.current = map
    // Dev builds only, for QA: lets tests inspect layers and project coordinates.
    if (import.meta.env.DEV) (window as unknown as Record<string, unknown>).__twMap = map
    map.touchZoomRotate.disableRotation()
    map.keyboard.disableRotation()
    map.addControl(new ScaleControl({ unit: 'metric', maxWidth: 90 }), 'bottom-left')
    map.addControl(new AttributionControl({ compact: true }), 'bottom-right')

    const made: Record<string, HTMLDivElement> = {}
    const markers = SITES.map((s) => {
      const el = document.createElement('div')
      el.style.width = el.style.height = '44px'
      made[s.id] = el
      return new Marker({ element: el, anchor: 'center' }).setLngLat([s.lon, s.lat]).addTo(map)
    })
    setEls(made)

    const h = health.current
    map.on('sourcedata', (e) => {
      if (e.dataType === 'source' && e.tile && typeof e.sourceId === 'string' && e.sourceId.startsWith('base-')) {
        h.okBases.add(e.sourceId.slice(5) as BaseMap)
        if (e.sourceId === baseId(h.base)) setTileFail(false)
      }
    })
    map.on('error', (e) => {
      const err = e as unknown as { sourceId?: string; error?: Error }
      if (/webgl/i.test(err.error?.message ?? '')) setNoWebGL(true)
      if (err.sourceId?.startsWith('base-') && ++h.errors >= 6 && !h.okBases.has(h.base)) setTileFail(true)
    })
    const onMove = (e: { lngLat: { lat: number; lng: number } }) => {
      if (coordRef.current) coordRef.current.textContent = `${e.lngLat.lat.toFixed(3)}°, ${e.lngLat.lng.toFixed(3)}°`
    }
    map.on('mousemove', onMove)
    // Screening patches: pointer feedback and selection. The layer may not exist yet; MapLibre accepts the listener early.
    map.on('click', PATCH_LAYER, (e) => latest.current.live?.setPatchId((e.features?.[0]?.properties?.id as string | undefined) ?? null))
    map.on('mouseenter', PATCH_LAYER, () => { map.getCanvas().style.cursor = 'pointer' })
    map.on('mouseleave', PATCH_LAYER, () => { map.getCanvas().style.cursor = '' })
    const onZoom = () => {
      if (zoomRef.current) zoomRef.current.textContent = map.getZoom().toFixed(1)
    }
    map.on('zoom', onZoom)
    onZoom()

    // Keep the whole world framed while the layout settles/resizes, until the user (or a selection) moves the camera.
    let userMoved = false
    let fitting = false
    map.on('movestart', () => { if (!fitting) userMoved = true })
    let raf = 0
    const ro = new ResizeObserver(() => {
      fitting = true // resize() also emits movestart
      map.resize()
      // Never zoom out past the point where the world fills the container (no blank margins, no seams).
      map.setMinZoom(Math.max(0, Math.log2(Math.max(host.clientWidth, host.clientHeight, 1) / 512)))
      fitting = false
      // Fit on the next frame so MapLibre's transform has the final container size.
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        if (userMoved || host.clientWidth === 0) return
        fitting = true
        map.fitBounds(WORLD, { padding: 24, duration: 0 })
        fitting = false
      })
    })
    ro.observe(host)

    return () => {
      ro.disconnect()
      markers.forEach((m) => m.remove())
      map.remove()
      mapRef.current = null
    }
  }, [])

  /* ── basemap / relief switching + tile-health watchdog ── */
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const h = health.current
    h.base = baseMap
    h.errors = 0
    setTileFail(false)
    const apply = () => BASE_KEYS.forEach((b) => map.setLayoutProperty(baseId(b), 'visibility', b === baseMap ? 'visible' : 'none'))
    if (map.isStyleLoaded()) apply()
    else map.once('load', apply)
    const t = window.setTimeout(() => {
      if (!h.okBases.has(baseMap) && (h.errors > 0 || !map.isSourceLoaded(baseId(baseMap)))) setTileFail(true)
    }, TILE_TIMEOUT_MS)
    return () => window.clearTimeout(t)
  }, [baseMap])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const run = () => setRelief(map, relief)
    if (map.isStyleLoaded()) run()
    else map.once('load', run)
  }, [relief])

  /* ── Layer 3 results: sources and layers are added, updated and removed in place; the map is never rebuilt ── */
  const liveOverlay = props.live?.overlay.status === 'done' ? props.live.overlay.data : null
  const liveScreen = props.live?.screen.status === 'done' ? props.live.screen.data : null
  const livePatch = props.live?.patchId ?? null
  const liveFit = props.live?.fit ?? null
  useEffect(() => { if (mapRef.current) syncOverlay(mapRef.current, liveOverlay) }, [liveOverlay])
  useEffect(() => { if (mapRef.current) syncScreen(mapRef.current, liveScreen, livePatch) }, [liveScreen]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (mapRef.current) setSelectedPatch(mapRef.current, livePatch) }, [livePatch])
  useEffect(() => {
    if (mapRef.current && liveFit) fitCoords(mapRef.current, liveFit.coords, { top: 56, left: 56, right: 72, bottom: 56 + latest.current.bottomPad })
  }, [liveFit])

  /* ── camera: eased fly to the selected site (instant under reduced motion) ── */
  useEffect(() => {
    const map = mapRef.current
    const s = siteById(selectedId)
    if (!map || !s) return
    const opts = {
      center: [s.lon, s.lat] as [number, number],
      zoom: Math.max(map.getZoom(), 6.2),
      padding: { top: 0, left: 0, right: 0, bottom: latest.current.bottomPad },
    }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) map.jumpTo(opts)
    else map.flyTo({ ...opts, duration: 1800, curve: 1.5, essential: true })
  }, [selectedId])

  /* ── marker visibility / stacking follows filters, selection and list hover ── */
  useEffect(() => {
    for (const [id, el] of Object.entries(els)) {
      el.style.display = visibleIds.has(id) || id === selectedId ? '' : 'none'
      el.style.zIndex = id === selectedId ? '3' : id === hoverId ? '2' : ''
    }
  }, [els, visibleIds, selectedId, hoverId])

  const shown = SITES.filter((s) => visibleIds.has(s.id) || s.id === selectedId)
  const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const fitSites = () => {
    const map = mapRef.current
    if (!map || shown.length === 0) return
    const duration = reduced() ? 0 : 900
    if (shown.length === 1) return void map.flyTo({ center: [shown[0].lon, shown[0].lat], zoom: 5, duration })
    const b = new LngLatBounds()
    shown.forEach((s) => b.extend([s.lon, s.lat]))
    map.fitBounds(b, { padding: { top: 56, left: 56, right: 72, bottom: 56 + props.bottomPad }, duration, maxZoom: 8 })
  }
  const focusSelected = () => {
    const s = siteById(selectedId)
    const map = mapRef.current
    if (!s || !map) return
    const opts = { center: [s.lon, s.lat] as [number, number], zoom: Math.max(map.getZoom(), 6.2), padding: { top: 0, left: 0, right: 0, bottom: props.bottomPad } }
    if (reduced()) map.jumpTo(opts)
    else map.flyTo({ ...opts, duration: 900, essential: true })
  }

  if (noWebGL) {
    return (
      <div className="relative h-full w-full">
        <SchematicMap sites={shown} selectedId={selectedId} statuses={statuses} onSelect={onSelect} />
        <p role="status" className="absolute inset-x-3 bottom-[calc(var(--sheet-offset,0px)+12px)] mx-auto max-w-md rounded-[var(--radius-md)] border border-[var(--line-strong)] bg-ink-900/90 px-3 py-2 text-[12px] text-silver-300">
          Interactive map unavailable (WebGL not supported) — showing a schematic graticule. Candidate sites remain fully usable.
        </p>
      </div>
    )
  }

  return (
    <div className="tw-map relative h-full w-full">
      <style>{`.tw-map .maplibregl-ctrl-bottom-left,.tw-map .maplibregl-ctrl-bottom-right{margin-bottom:var(--sheet-offset,0px)}`}</style>
      <div ref={hostRef} className="absolute inset-0" role="region" aria-label="Interactive map of candidate Earth analog sites" />
      {SITES.map((s) =>
        els[s.id]
          ? createPortal(
              <SiteMarker site={s} status={statuses.get(s.id) ?? 'not-assessed'} selected={s.id === selectedId} hover={s.id === hoverId} compared={compareIds.includes(s.id)} onSelect={onSelect} />,
              els[s.id],
              s.id,
            )
          : null,
      )}

      <MapControls
        nFilters={props.nFilters}
        onFilters={props.onFilters}
        onZoom={(d) => (d > 0 ? mapRef.current?.zoomIn() : mapRef.current?.zoomOut())}
        onFit={fitSites}
        onFocus={selectedId ? focusSelected : undefined}
        livePanel={props.livePanel}
        liveActive={!!(liveOverlay || liveScreen)}
      />
      {props.liveUi}

      {tileFail && !bannerOff && (
        <div role="status" className="absolute top-3 left-1/2 z-10 flex w-[min(520px,calc(100%-130px))] -translate-x-1/2 items-start gap-2 glass rounded-[var(--radius-md)] border border-amber/40 py-1 pr-1 pl-3 text-[12px] leading-snug text-silver-200 shadow-[var(--shadow-pop)] max-lg:top-[60px] max-lg:w-[calc(100%-24px)]">
          <span className="flex-1 py-1">Basemap imagery unavailable — showing schematic graticule. Candidate sites remain fully usable.</span>
          <button type="button" onClick={() => setBannerOff(true)} aria-label="Dismiss notice" className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-silver-400 transition-[color,transform] hover:text-paper active:scale-95"><X size={14} aria-hidden /></button>
        </div>
      )}

      <div className="pointer-events-none absolute bottom-[calc(var(--sheet-offset,0px)+40px)] left-2.5 z-10 max-w-[calc(100%-20px)] space-y-0.5 rounded-[var(--radius-sm)] bg-ink-900/80 px-2 py-1 backdrop-blur">
        <p className="mono text-[12px] text-silver-300"><span aria-hidden>⌖ </span><span ref={coordRef}>—</span> · z<span ref={zoomRef}>1.0</span></p>
      </div>
    </div>
  )
}
