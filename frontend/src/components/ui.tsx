import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, CircleCheck, CircleDashed, CircleX, X } from 'lucide-react'
import { useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { STATUS_LABEL } from '../lib/assess'
import { DUR, EASE } from '../lib/motion'
import type { Status } from '../data/types'

export const cx = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(' ')

/* ─────────────── Button ─────────────── */
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost'; size?: 'md' | 'sm'; paper?: boolean }
export function Button({ variant = 'secondary', size = 'md', paper, className, ...p }: BtnProps) {
  const base = 'inline-flex items-center justify-center gap-2 rounded-[var(--radius-md)] font-medium whitespace-nowrap select-none transition-[background-color,border-color,transform,color] duration-[var(--duration-fast)] ease-[var(--ease-out)] active:scale-[0.97] disabled:opacity-40 disabled:pointer-events-none'
  const sz = size === 'md' ? 'min-h-11 px-4 text-[15px]' : 'min-h-11 md:min-h-9 px-3 text-[13px]'
  const v = {
    primary: 'bg-amber text-ink-900 hover:bg-[#efb872]',
    secondary: paper ? 'border border-[var(--line-strong)] text-graphite hover:bg-black/5' : 'border border-[var(--line-strong)] text-paper hover:bg-white/8',
    ghost: paper ? 'text-graphite hover:bg-black/5' : 'text-silver-300 hover:text-paper hover:bg-white/8',
  }[variant]
  return <button type="button" className={cx(base, sz, v, className)} {...p} />
}

/* ─────────────── Status badge: glyph + label + colour ─────────────── */
const STATUS_STYLE: Record<Status, { Icon: typeof CircleCheck; dark: string; paper: string }> = {
  potential: { Icon: CircleCheck, dark: 'text-ok border-ok/40 bg-ok/10', paper: 'text-ok-deep border-ok-deep/40 bg-ok-deep/8' },
  'not-suitable': { Icon: CircleX, dark: 'text-bad border-bad/40 bg-bad/10', paper: 'text-bad-deep border-bad-deep/40 bg-bad-deep/8' },
  'not-assessed': { Icon: CircleDashed, dark: 'text-silver-300 border-dashed border-silver-500 bg-white/4', paper: 'text-graphite-soft border-dashed border-graphite-soft bg-black/4' },
}
export function StatusBadge({ status, paper, compact, label }: { status: Status; paper?: boolean; compact?: boolean; label?: string }) {
  const { Icon, dark, paper: p } = STATUS_STYLE[status]
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[12px] font-medium leading-5 whitespace-nowrap', paper ? p : dark)}>
      <Icon size={compact ? 13 : 14} aria-hidden strokeWidth={2.2} />
      {label ?? STATUS_LABEL[status]}
    </span>
  )
}
export function StatusGlyph({ status, size = 16 }: { status: Status; size?: number }) {
  const { Icon, dark } = STATUS_STYLE[status]
  return (
    <span className={cx('inline-flex', dark.split(' ')[0])} role="img" aria-label={STATUS_LABEL[status]}>
      <Icon size={size} strokeWidth={2.2} />
    </span>
  )
}

/* ─────────────── Segmented control (radiogroup) ─────────────── */
export function Segmented<T extends string | number>({ label, value, options, onChange, paper }: { label: string; value: T; options: { value: T; label: ReactNode; title?: string }[]; onChange: (v: T) => void; paper?: boolean }) {
  const id = useId()
  return (
    <div role="radiogroup" aria-label={label} className={cx('inline-flex rounded-[var(--radius-md)] border border-[var(--line)] p-0.5', paper ? 'bg-black/4' : 'bg-white/4')}>
      {options.map((o) => {
        const on = o.value === value
        return (
          <button key={String(o.value)} type="button" role="radio" aria-checked={on} title={o.title} onClick={() => onChange(o.value)}
            className={cx('relative min-h-10 rounded-[8px] px-3 text-[13px] font-medium transition-colors', on ? (paper ? 'text-graphite' : 'text-paper') : paper ? 'text-graphite-soft hover:text-graphite' : 'text-silver-400 hover:text-paper')}>
            {on && <motion.span layoutId={`seg-${id}`} className={cx('absolute inset-0 rounded-[8px] border border-[var(--line-strong)]', paper ? 'bg-white shadow-sm' : 'bg-ink-700')} transition={{ type: 'spring', stiffness: 500, damping: 40 }} />}
            <span className="relative">{o.label}</span>
          </button>
        )
      })}
    </div>
  )
}

/* ─────────────── Slider ─────────────── */
export function Slider({ label, value, min, max, step = 1, unit = '', onChange, hint, format }: { label: string; value: number; min: number; max: number; step?: number; unit?: string; onChange: (v: number) => void; hint?: string; format?: (v: number) => string }) {
  const id = useId()
  const txt = format ? format(value) : `${value}${unit}`
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-[13px] font-medium text-silver-200">{label}</label>
        <output htmlFor={id} className="mono text-[13px] text-amber">{txt}</output>
      </div>
      <input id={id} type="range" min={min} max={max} step={step} value={value} aria-valuetext={txt}
        style={{ ['--fill' as string]: `${((value - min) / (max - min)) * 100}%` }}
        onChange={(e) => onChange(+e.target.value)} />
      {hint && <p className="-mt-1 text-[12px] leading-snug text-silver-500">{hint}</p>}
    </div>
  )
}

/* ─────────────── Toggle switch ─────────────── */
export function Toggle({ label, checked, onChange, hint }: { label: string; checked: boolean; onChange: (b: boolean) => void; hint?: string }) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="flex min-h-11 w-full items-center justify-between gap-3 text-left">
      <span>
        <span className="block text-[13px] font-medium text-silver-200">{label}</span>
        {hint && <span className="block text-[12px] text-silver-500">{hint}</span>}
      </span>
      <span className={cx('relative h-6 w-10 shrink-0 rounded-full border transition-colors duration-[var(--duration-base)]', checked ? 'border-amber bg-amber/25' : 'border-[var(--line-strong)] bg-white/5')}>
        <span className={cx('absolute top-0.5 h-5 w-5 rounded-full transition-[left,background-color] duration-[var(--duration-base)] ease-[var(--ease-out)]', checked ? 'left-[18px] bg-amber' : 'left-0.5 bg-silver-400')} />
      </span>
    </button>
  )
}

/* ─────────────── Native select, styled ─────────────── */
export function Select({ label, value, onChange, options, id: idProp }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string; disabled?: boolean }[]; id?: string }) {
  const gen = useId()
  const id = idProp ?? gen
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[13px] font-medium text-silver-200">{label}</label>
      <div className="relative">
        <select id={id} value={value} onChange={(e) => onChange(e.target.value)}
          className="min-h-11 w-full appearance-none rounded-[var(--radius-md)] border border-[var(--line-strong)] bg-ink-800 py-2 pr-10 pl-3 text-[14px] text-paper transition-colors hover:border-silver-500">
          {options.map((o) => <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>)}
        </select>
        <ChevronDown size={16} aria-hidden className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-silver-400" />
      </div>
    </div>
  )
}

/* ─────────────── Tabs ─────────────── */
export function Tabs<T extends string>({ label, value, tabs, onChange, paper }: { label: string; value: T; tabs: { id: T; label: string }[]; onChange: (v: T) => void; paper?: boolean }) {
  const id = useId()
  const refs = useRef<Record<string, HTMLButtonElement | null>>({})
  const onKey = (e: React.KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === value)
    const n = e.key === 'ArrowRight' ? (i + 1) % tabs.length : e.key === 'ArrowLeft' ? (i - 1 + tabs.length) % tabs.length : e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : -1
    if (n < 0) return
    e.preventDefault()
    onChange(tabs[n].id)
    refs.current[tabs[n].id]?.focus()
  }
  return (
    <div role="tablist" aria-label={label} onKeyDown={onKey} className="flex gap-1 overflow-x-auto border-b border-[var(--line)] scroll-thin">
      {tabs.map((t) => {
        const on = t.id === value
        return (
          <button key={t.id} ref={(el) => { refs.current[t.id] = el }} role="tab" id={`${id}-${t.id}`} aria-selected={on} tabIndex={on ? 0 : -1} type="button" onClick={() => onChange(t.id)}
            className={cx('relative min-h-11 shrink-0 px-3 text-[14px] font-medium transition-colors', on ? (paper ? 'text-graphite' : 'text-paper') : paper ? 'text-graphite-soft hover:text-graphite' : 'text-silver-400 hover:text-paper')}>
            {t.label}
            {on && <motion.span layoutId={`tab-${id}`} className="absolute inset-x-2 -bottom-px h-0.5 rounded bg-amber" transition={{ type: 'spring', stiffness: 500, damping: 40 }} />}
          </button>
        )
      })}
    </div>
  )
}

/* ─────────────── Disclosure (expandable explanation) ─────────────── */
export function Disclosure({ title, meta, children, open, onToggle, paper, defaultOpen }: { title: ReactNode; meta?: ReactNode; children: ReactNode; open?: boolean; onToggle?: (o: boolean) => void; paper?: boolean; defaultOpen?: boolean }) {
  const [local, setLocal] = useState(!!defaultOpen)
  const isOpen = open ?? local
  const id = useId()
  return (
    <div className="border-b border-[var(--line)]">
      <button type="button" aria-expanded={isOpen} aria-controls={id} onClick={() => (onToggle ? onToggle(!isOpen) : setLocal(!isOpen))}
        className={cx('flex min-h-11 w-full items-center gap-3 py-2.5 text-left transition-colors', paper ? 'hover:bg-black/3' : 'hover:bg-white/3')}>
        <span className="min-w-0 flex-1">{title}</span>
        {meta}
        <ChevronDown size={16} aria-hidden className={cx('shrink-0 transition-transform duration-[var(--duration-base)] ease-[var(--ease-out)]', isOpen && 'rotate-180')} />
      </button>
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div id={id} initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: DUR.base, ease: EASE }} className="overflow-hidden">
            <div className="pb-4 text-[14px] leading-relaxed text-silver-300 [.paper_&]:text-graphite-soft">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
/* ─────────────── Modal (native <dialog>: focus trap, Esc, inert background) ─────────────── */
export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog ref={ref} onClose={onClose} onClick={(e) => e.target === ref.current && onClose()} aria-labelledby="modal-title"
      className="tw-dialog m-auto max-h-[88dvh] w-[min(640px,calc(100vw-24px))] overflow-hidden rounded-[var(--radius-lg)] border border-[var(--line-strong)] bg-ink-850 p-0 text-paper shadow-[var(--shadow-pop)] backdrop:bg-black/60">
      <div className="flex items-center justify-between border-b border-[var(--line)] px-5 py-3">
        <h2 id="modal-title" className="text-[17px] font-semibold">{title}</h2>
        <button type="button" onClick={onClose} aria-label="Close" className="grid h-11 w-11 place-items-center rounded-full text-silver-300 hover:bg-white/8 hover:text-paper"><X size={18} aria-hidden /></button>
      </div>
      <div className="scroll-thin max-h-[calc(88dvh-64px)] overflow-y-auto px-5 py-4">{children}</div>
    </dialog>
  )
}

/* ─────────────── Small layout helpers ─────────────── */
export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cx('eyebrow', className)}>{children}</p>
}
/** A titled region: a hairline rule and a heading — structure without a box. Pass  for the rare surface that must float. */
/** A titled region: a hairline rule and a heading, structure without a box. `boxed` is for the rare surface that must float. */
export function Panel({ title, aside, children, className, boxed }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string; boxed?: boolean }) {
  return (
    <section className={cx(boxed ? 'rounded-[var(--radius-lg)] border border-[var(--line)] bg-ink-850 p-4' : 'border-t border-[var(--line)] pt-4', className)}>
      {title && (
        <header className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-[13px] font-medium text-silver-300">{title}</h2>
          {aside}
        </header>
      )}
      <div>{children}</div>
    </section>
  )
}
export function ProtoNote({ children, paper }: { children?: ReactNode; paper?: boolean }) {
  return (
    <p className={cx('mono text-[12px] leading-relaxed', paper ? 'text-graphite-soft' : 'text-silver-500')}>
      {children ?? 'ILLUSTRATIVE PROTOTYPE DATA — not validated NASA results.'}
    </p>
  )
}
export function EmptyState({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 px-6 py-16 text-center">
      <div className="grid h-12 w-12 place-items-center rounded-full border border-dashed border-silver-500 text-silver-400"><CircleDashed size={22} aria-hidden /></div>
      <h2 className="text-[20px] font-semibold">{title}</h2>
      <p className="text-[14px] text-silver-400">{body}</p>
      {action}
    </div>
  )
}
