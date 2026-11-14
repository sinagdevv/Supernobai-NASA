import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Crosshair, Layers, Maximize2, Minus, Mountain, Plus, SlidersHorizontal } from 'lucide-react'
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { cx } from '../ui'
import { LayerPopover } from './LayerPanel'

const btn =
  'relative grid h-11 w-11 place-items-center text-silver-200 transition-[color,background-color,transform] duration-[var(--duration-fast)] ease-[var(--ease-out)] hover:bg-white/8 hover:text-paper active:scale-[0.94]'

function Btn({ label, onClick, children, pressed, expanded, controls, className }: { label: string; onClick: () => void; children: ReactNode; pressed?: boolean; expanded?: boolean; controls?: string; className?: string }) {
  return (
    <button type="button" aria-label={label} title={label} aria-pressed={pressed} aria-expanded={expanded} aria-controls={controls} onClick={onClick} className={cx(btn, className)}>
      {children}
    </button>
  )
}

/** One small control cluster: filters (phones), layers, zoom, fit to candidates, focus selected. */
export function MapControls({ nFilters, onFilters, onZoom, onFit, onFocus, livePanel, liveActive }: { nFilters: number; onFilters: () => void; onZoom: (dir: 1 | -1) => void; onFit: () => void; onFocus?: () => void; livePanel?: ReactNode; liveActive?: boolean }) {
  const [which, setWhich] = useState<'layers' | 'live' | null>(null)
  const open = which !== null
  const setOpen = (o: boolean) => { if (!o) setWhich(null) }
  const reduce = useReducedMotion()
  const id = useId()
  const wrap = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const away = (e: PointerEvent) => !wrap.current?.contains(e.target as Node) && setOpen(false)
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('pointerdown', away)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('pointerdown', away)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  return (
    <div ref={wrap} className="absolute top-2.5 right-2.5 z-10">
      <div role="group" aria-label="Map controls" className="glass flex flex-col divide-y divide-[var(--line)] overflow-hidden rounded-[var(--radius-md)] border border-[var(--line-strong)] shadow-[var(--shadow-pop)]">
        <Btn label={nFilters ? `Filters (${nFilters} active)` : 'Filters'} onClick={onFilters} className="lg:hidden">
          <SlidersHorizontal size={18} aria-hidden />
          {nFilters > 0 && <span className="mono absolute top-1 right-1 grid h-4 min-w-4 place-items-center rounded-full bg-amber px-1 text-[12px] leading-none text-ink-900">{nFilters}</span>}
        </Btn>
        <Btn label="Map layers" expanded={which === 'layers'} controls={id} onClick={() => setWhich(which === 'layers' ? null : 'layers')} className={which === 'layers' ? 'bg-white/8 text-paper' : undefined}><Layers size={18} aria-hidden /></Btn>
        {livePanel && (
          <Btn label="Live terrain from the Layer 3 service" expanded={which === 'live'} controls={id} onClick={() => setWhich(which === 'live' ? null : 'live')} className={which === 'live' ? 'bg-white/8 text-paper' : undefined}>
            <Mountain size={18} aria-hidden />
            {liveActive && <i aria-hidden className="absolute top-2 right-2 h-2 w-2 rounded-full bg-cyan" />}
          </Btn>
        )}
        <Btn label="Zoom in" onClick={() => onZoom(1)}><Plus size={18} aria-hidden /></Btn>
        <Btn label="Zoom out" onClick={() => onZoom(-1)}><Minus size={18} aria-hidden /></Btn>
        <Btn label="Fit to candidates" onClick={onFit}><Maximize2 size={17} aria-hidden /></Btn>
        {onFocus && <Btn label="Focus selected site" onClick={onFocus}><Crosshair size={18} aria-hidden /></Btn>}
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id}
            role="region"
            aria-label={which === 'live' ? 'Live terrain' : 'Map layers'}
            // Opens from the Layers button's corner, beside the cluster; never from scale 0.
            style={{ transformOrigin: 'top right' }}
            initial={reduce ? { opacity: 0 } : { opacity: 0, scale: 0.96 }}
            animate={reduce ? { opacity: 1 } : { opacity: 1, scale: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.1 } }}
            transition={{ duration: 0.16, ease: [0.23, 1, 0.32, 1] }}
            className="glass absolute top-0 right-[calc(100%+8px)] max-h-[calc(100dvh-var(--topbar-h)-var(--tabbar-h)-var(--sheet-offset,0px)-24px)] overflow-y-auto rounded-[var(--radius-md)] border border-[var(--line-strong)] p-3 shadow-[var(--shadow-pop)]"
          >
            {which === 'live' ? livePanel : <LayerPopover />}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
