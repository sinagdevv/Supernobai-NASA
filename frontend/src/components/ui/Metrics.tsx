import type { ReactNode } from 'react'
import { CircleDashed, CircleMinus } from 'lucide-react'
import type { Status } from '../../data/types'
import { StatusBadge, cx } from '../ui'

/** One measure for both sides, what it has to meet, and the result. Values arrive formatted: units and thresholds are the caller's, unchanged. */
export type MetricRowData = {
  label: ReactNode
  ref?: ReactNode
  cand: ReactNode
  need?: ReactNode
  /** An assessed criterion shows its status badge; anything else is plain context. */
  status?: Status
  /** For rows that are not a criterion: what the result column says. */
  note?: string
}

const Cell = ({ label, children, tone }: { label: string; children: ReactNode; tone?: 'earth' | 'moon' }) => (
  <div className="min-w-0">
    <p className="text-xs text-silver-400">{label}</p>
    <p className={cx('mono mt-0.5 text-[17px] leading-tight [overflow-wrap:anywhere]', tone === 'earth' ? 'text-cyan' : 'text-silver-200')}>{children}</p>
  </div>
)

/** A titled group of metric rows, set off by a hairline. Reused wherever two datasets are read side by side. */
export function MetricGroup({ title, rows, refLabel, candLabel }: { title: ReactNode; rows: MetricRowData[]; refLabel: string; candLabel: string }) {
  return (
    <section className="border-t border-[var(--line)] pt-3 pb-5">
      <h3 className="text-[15px] font-semibold">{title}</h3>
      <ul className="mt-2 divide-y divide-[var(--line)]">
        {rows.map((r, i) => (
          <li key={i} className="grid grid-cols-2 gap-x-4 gap-y-2 py-2.5">
            <p className="col-span-2 text-[13px] text-silver-300">{r.label}</p>
            <Cell label={refLabel} tone="moon">{r.ref ?? '—'}</Cell>
            <Cell label={candLabel} tone="earth">{r.cand}</Cell>
            <div className="col-span-2 flex flex-wrap items-center gap-x-3 gap-y-1">
              {r.status ? <StatusBadge status={r.status} compact /> : <span className="inline-flex items-center gap-1.5 text-xs text-silver-300">{r.note ? <CircleDashed size={13} aria-hidden /> : <CircleMinus size={13} aria-hidden />}{r.note ?? 'Context, not a criterion'}</span>}
              {r.need && <span className="mono text-xs text-silver-400">needs {r.need}</span>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
