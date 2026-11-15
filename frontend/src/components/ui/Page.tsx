import type { ReactNode } from 'react'
import { cx } from '../ui'

/** The one h1 of a screen: planetary context above, a title, a lede capped at a readable line length, and the screen's primary action. */
export function PageHeader({ eyebrow, title, lede, actions, className }: { eyebrow?: ReactNode; title: string; lede?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <header className={cx('flex flex-wrap items-end justify-between gap-x-8 gap-y-4', className)}>
      <div className="min-w-0">
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        <h1 className="font-display text-[38px] font-medium md:text-[48px]">{title}</h1>
        {lede && <p className="mt-2 max-w-[62ch] text-[15px] leading-relaxed text-silver-300">{lede}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-3">{actions}</div>}
    </header>
  )
}

/** How to read what is on a screen: what is measured, what is computed and not validated, what is illustrative. A hairline above, no box. */
export function ReadingKey({ items, label = 'How to read this screen', className }: { items: { term: ReactNode; text: ReactNode }[]; label?: string; className?: string }) {
  return (
    <section aria-label={label} className={cx('grid gap-x-8 gap-y-4 border-t border-[var(--line)] pt-5 sm:grid-cols-3', className)}>
      {items.map((it, i) => (
        <div key={i}>
          <p className="text-[14px] font-medium text-paper">{it.term}</p>
          <p className="mt-1 max-w-[46ch] text-[13px] leading-relaxed text-silver-300">{it.text}</p>
        </div>
      ))}
    </section>
  )
}
