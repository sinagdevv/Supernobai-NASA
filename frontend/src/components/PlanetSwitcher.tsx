import { motion } from 'motion/react'
import { useId, useRef, type KeyboardEvent } from 'react'
import { PLANET_COPY, usePlanet, type Planet } from '../lib/planet'
import { cx } from './ui'

/** Moon: a disc lit from the left by a low sun, with two craters. Drawn for 24 px, stroke and fill in currentColor. */
function MoonIcon({ size }: { size: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3a9 9 0 0 0 0 18 5.5 9 0 0 1 0-18Z" fill="currentColor" stroke="none" opacity="0.9" />
      <circle cx="15.6" cy="9.2" r="1.5" strokeWidth="1.2" />
      <circle cx="14.2" cy="15.4" r="1" strokeWidth="1.2" />
    </svg>
  )
}

/** Mars: a disc with a flat-topped mesa on its horizon, the landform the Martian profile is built around. */
function MarsIcon({ size }: { size: number }) {
  const id = useId()
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} aria-hidden fill="none" stroke="currentColor" strokeWidth="1.5">
      <clipPath id={id}><circle cx="12" cy="12" r="9" /></clipPath>
      <circle cx="12" cy="12" r="9" />
      <path clipPath={`url(#${id})`} d="M2 16.5h5.6l1.5-4.4h5.8l1.6 4.4H22V22H2Z" fill="currentColor" stroke="none" opacity="0.9" />
      <path d="M6 9.5h2.6M13 7h3.4" strokeWidth="1.2" strokeLinecap="round" opacity="0.55" />
    </svg>
  )
}

const OPTIONS: { value: Planet; sub: string; Icon: (p: { size: number }) => React.ReactElement }[] = [
  { value: 'moon', sub: 'Primary mission', Icon: MoonIcon },
  { value: 'mars', sub: 'Regional terrain', Icon: MarsIcon },
]

/**
 * Level 1 of the navigation: which planet the whole workspace is about. Two options, one selected, arrow keys move the selection.
 * `hero` is the larger landing-page form with the one-line role of each planet; `header` is the compact form for the workspace.
 */
export function PlanetSwitcher({ variant = 'header', className }: { variant?: 'hero' | 'header'; className?: string }) {
  const { planet, setPlanet } = usePlanet()
  const id = useId()
  const refs = useRef<(HTMLButtonElement | null)[]>([])
  const hero = variant === 'hero'

  const onKey = (e: KeyboardEvent) => {
    const i = OPTIONS.findIndex((o) => o.value === planet)
    const n = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? (i + 1) % OPTIONS.length : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? (i - 1 + OPTIONS.length) % OPTIONS.length : -1
    if (n < 0) return
    e.preventDefault()
    setPlanet(OPTIONS[n].value)
    refs.current[n]?.focus()
  }

  return (
    <div role="radiogroup" aria-label="Planetary target" onKeyDown={onKey} className={cx('relative inline-flex rounded-[var(--radius-lg)] border border-[var(--line-strong)] bg-white/[0.035] p-1', className)}>
      {OPTIONS.map((o, i) => {
        const on = o.value === planet
        const copy = PLANET_COPY[o.value]
        return (
          <button key={o.value} ref={(el) => { refs.current[i] = el }} type="button" role="radio" aria-checked={on} tabIndex={on ? 0 : -1} onClick={() => setPlanet(o.value)}
            className={cx('relative flex items-center rounded-[calc(var(--radius-lg)-3px)] text-left transition-[color,transform] duration-[var(--duration-fast)] ease-[var(--ease-out)] active:scale-[0.97]',
              hero ? 'min-h-12 gap-3 px-4' : 'min-h-10 gap-2 px-2 sm:px-3', on ? 'text-paper' : 'text-silver-400 hover:text-paper')}>
            {on && <motion.span layoutId={`planet-${id}`} aria-hidden className="absolute inset-0 rounded-[calc(var(--radius-lg)-3px)] border border-[var(--line-strong)] bg-ink-700" transition={{ type: 'spring', duration: 0.34, bounce: 0.08 }}>
              <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full" style={{ background: o.value === 'mars' ? '#c9876a' : 'var(--color-silver-300)' }} />
            </motion.span>}
            <span className="relative" style={{ color: on ? (o.value === 'mars' ? '#d99a7c' : 'var(--color-silver-200)') : undefined }}><o.Icon size={hero ? 24 : 20} /></span>
            <span className="relative flex flex-col leading-tight">
              <span className={cx('font-medium', hero ? 'text-[15px]' : 'text-[14px]')}>{copy.label}</span>
              {hero && <span className="text-xs font-normal text-silver-400">{o.sub}</span>}
              {!hero && <span className="hidden text-xs font-normal text-silver-400 2xl:block">{o.sub}</span>}
            </span>
          </button>
        )
      })}
    </div>
  )
}
