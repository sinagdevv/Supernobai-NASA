import { useId, type ReactNode } from 'react'
import { Check } from 'lucide-react'
import { cx } from '../ui'

/** `target` is the id of the part of the page the step jumps to. (Hash links would change the route.) */
export type JourneyStep = { label: string; target: string }

/** A compact "where am I" indicator: steps before the current one are done, the current one is marked, links jump to each part of the page. */
export function Journey({ steps, current, label }: { steps: JourneyStep[]; current: number; label: string }) {
  return (
    <nav aria-label={label}>
      <p className="mono text-xs text-silver-300 sm:hidden">Step {current + 1} of {steps.length} · {steps[current].label}</p>
      <ol className="hidden items-center gap-x-1 sm:flex">
        {steps.map((s, i) => {
          const done = i < current, on = i === current
          return (
            <li key={s.label} className="flex items-center gap-1">
              {i > 0 && <span aria-hidden className={cx('h-px w-4 lg:w-8', done || on ? 'bg-silver-400' : 'bg-[var(--line-strong)]')} />}
              <button type="button" onClick={() => document.getElementById(s.target)?.scrollIntoView({ block: 'start' })} aria-current={on ? 'step' : undefined} className={cx('flex min-h-9 items-center gap-2 rounded-full pr-2.5 pl-1 text-[13px] transition-colors', on ? 'font-medium text-paper' : 'text-silver-300 hover:text-paper')}>
                <span aria-hidden className={cx('mono grid h-6 w-6 place-items-center rounded-full border text-xs', on ? 'border-amber bg-amber text-ink-900' : done ? 'border-silver-400 text-silver-200' : 'border-dashed border-silver-500 text-silver-400')}>{done ? <Check size={13} strokeWidth={3} /> : i + 1}</span>
                {s.label}
                {done && <span className="sr-only"> (done)</span>}
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

/** One group of research parameters: a number and title beside its controls, set off by a hairline. */
export function ParamGroup({ id, n, title, hint, children }: { id?: string; n: number; title: string; hint?: ReactNode; children: ReactNode }) {
  const hid = useId()
  return (
    <section id={id} aria-labelledby={hid} className="grid gap-x-8 gap-y-3 border-t border-[var(--line)] py-5 md:grid-cols-[10rem_minmax(0,1fr)]">
      <div>
        <h3 id={hid} className="flex items-baseline gap-2 text-[15px] font-semibold"><span aria-hidden className="mono text-xs font-normal text-silver-400">{n}</span>{title}</h3>
        {hint && <p className="mt-1 text-[13px] leading-snug text-silver-400">{hint}</p>}
      </div>
      <div className="min-w-0">{children}</div>
    </section>
  )
}
