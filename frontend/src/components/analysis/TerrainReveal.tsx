import { animate, useInView, useReducedMotion, type AnimationPlaybackControls } from 'motion/react'
import { useEffect, useId, useRef, useState } from 'react'
import { EASE } from '../../lib/motion'
import { TerrainCanvas } from '../TerrainCanvas'

/**
 * Moon ← divider → Earth. The Earth layer is revealed with clip-path. It opens with a single sweep to 50% on first view;
 * any user input (drag on the image, or the slider) cancels that sweep immediately and takes over.
 */
export function TerrainReveal({ moonSeed, earthSeed, moonLabel, earthLabel, el = 3, az = 200 }: { moonSeed: number; earthSeed: number; moonLabel: string; earthLabel: string; el?: number; az?: number }) {
  const [pos, setPos] = useState(100)
  const ref = useRef<HTMLDivElement>(null)
  const stage = useRef<HTMLDivElement>(null)
  const sweep = useRef<AnimationPlaybackControls | null>(null)
  const dragging = useRef(false)
  const inView = useInView(ref, { once: true, amount: 0.4 })
  const reduce = useReducedMotion()
  const id = useId()

  useEffect(() => {
    if (!inView) return
    if (reduce) return setPos(50)
    sweep.current = animate(100, 50, { duration: 0.8, ease: EASE, onUpdate: setPos })
    return () => sweep.current?.stop()
  }, [inView, reduce])

  const take = (v: number) => {
    sweep.current?.stop()
    setPos(Math.min(100, Math.max(0, v)))
  }
  const fromPointer = (e: React.PointerEvent) => {
    const r = stage.current!.getBoundingClientRect()
    take(((e.clientX - r.left) / r.width) * 100)
  }

  return (
    <div ref={ref}>
      <div
        ref={stage}
        onPointerDown={(e) => { dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); fromPointer(e) }}
        onPointerMove={(e) => dragging.current && fromPointer(e)}
        onPointerUp={() => (dragging.current = false)}
        onPointerCancel={() => (dragging.current = false)}
        className="relative aspect-[16/10] w-full cursor-ew-resize overflow-hidden rounded-[var(--radius-md)] bg-ink-950 [touch-action:pan-y] sm:aspect-[21/9]"
      >
        <div className="absolute inset-0"><TerrainCanvas kind="moon" seed={moonSeed} el={el} az={az} label={`Illustrative synthetic lunar-style terrain, ${moonLabel}`} /></div>
        <div className="absolute inset-0" style={{ clipPath: `inset(0 0 0 ${pos}%)` }}><TerrainCanvas kind="earth" seed={earthSeed} el={el} az={az} label={`Illustrative synthetic Earth-style terrain, ${earthLabel}`} /></div>
        <div aria-hidden className="pointer-events-none absolute inset-y-0 w-px bg-paper/80" style={{ left: `${pos}%` }}>
          <span className="absolute top-1/2 left-1/2 grid h-9 w-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border border-paper/80 bg-ink-900/85 text-[13px] text-paper">⇄</span>
        </div>
        <span className="pointer-events-none absolute top-3 left-3 rounded-[var(--radius-sm)] bg-ink-900/80 px-2 py-1 text-[12px] font-medium text-silver-200">Lunar reference</span>
        <span className="pointer-events-none absolute top-3 right-3 rounded-[var(--radius-sm)] bg-ink-900/80 px-2 py-1 text-[12px] font-medium text-cyan">Earth candidate</span>
        <span className="mono pointer-events-none absolute bottom-3 left-3 rounded-[var(--radius-sm)] bg-ink-900/80 px-2 py-1 text-[12px] text-silver-300">sun {el}° elev · {az}° az</span>
      </div>
      <div className="mt-1">
        <label htmlFor={id} className="sr-only">Reveal position: lunar reference on the left, Earth candidate on the right</label>
        <input id={id} type="range" min={0} max={100} value={Math.round(pos)} onChange={(e) => take(+e.target.value)} aria-valuetext={`${Math.round(pos)}% lunar reference visible`} style={{ ['--fill' as string]: `${pos}%` }} />
      </div>
      <p className="mono text-[12px] leading-relaxed text-silver-500">Illustrative synthetic terrain, not LRO or satellite data. 10 m/px, vertically exaggerated ×3. Same low-angle sun on both sides.</p>
    </div>
  )
}
