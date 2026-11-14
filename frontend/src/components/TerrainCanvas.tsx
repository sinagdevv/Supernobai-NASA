import { memo, useEffect, useRef } from 'react'
import { heightfield, PALETTES, paintTerrain, type TerrainKind } from '../lib/terrain'

interface Props {
  kind: TerrainKind
  seed: number
  /** Sun (or lamp) elevation / azimuth in degrees */
  el: number
  az: number
  w?: number
  h?: number
  exag?: number
  warm?: number
  className?: string
  label: string
}

/** Procedural terrain rendered with cast shadows. Repaints (rAF-coalesced) only when sun parameters change. */
export const TerrainCanvas = memo(function TerrainCanvas({ kind, seed, el, az, w = 224, h = 128, exag = 3, warm = 0, className, label }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const raf = useRef(0)
  useEffect(() => {
    cancelAnimationFrame(raf.current)
    raf.current = requestAnimationFrame(() => {
      const ctx = ref.current?.getContext('2d')
      if (ctx) paintTerrain(ctx, heightfield(kind, seed, w, h, exag), el, az, PALETTES[kind], warm)
    })
    return () => cancelAnimationFrame(raf.current)
  }, [kind, seed, w, h, exag, el, az, warm])
  return <canvas ref={ref} width={w} height={h} role="img" aria-label={label} className={className} style={{ width: '100%', height: '100%', display: 'block', objectFit: 'cover' }} />
})
