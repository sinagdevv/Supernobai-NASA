import type { ReactNode } from 'react'
import { SITES } from '../../data/sites'
import { useApp } from '../../lib/store'
import { Disclosure, EmptyState, StatusGlyph, cx } from '../ui'

/** Chart colours as literals (SVG attributes inside Recharts). Moon = silver, Earth reference = cyan, mission reference = amber. */
export const C = { moon: '#c5cad0', earth: '#80b7c4', ref: '#e4a95b', axis: '#8b939e', grid: 'rgba(255,255,255,0.08)', bg: '#151a20' }

export const tooltipStyle = { background: '#1b2027', border: '1px solid rgba(255,255,255,0.18)', borderRadius: 8, fontSize: 12, color: '#f4f3ef' }
export const tickStyle = { fill: C.axis, fontSize: 12 }

export const fmtCoord = (lat: number, lon: number) => `${Math.abs(lat).toFixed(2)}° ${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(2)}° ${lon >= 0 ? 'E' : 'W'}`

/** Source / caveat line. 12px, never smaller. */
export function Note({ children, paper }: { children: ReactNode; paper?: boolean }) {
  return <p className={cx('mono text-[12px] leading-relaxed', paper ? 'text-graphite-soft' : 'text-silver-500')}>{children}</p>
}

/* ─────────── Empty state with quick picks (no Earth site chosen yet) ─────────── */
export function NoSite({ what }: { what: string }) {
  const { select, results, assessments } = useApp()
  const picks = (results.length ? results : SITES.map((s) => s.id)).slice(0, 4)
  return (
    <EmptyState
      title="No Earth candidate selected"
      body={`Choose a site to open its ${what}. You can change it at any time in the Analog Explorer.`}
      action={
        <div className="mt-2 flex w-full flex-col gap-2">
          {picks.map((id) => {
            const s = SITES.find((x) => x.id === id)!
            return (
              <button key={id} type="button" onClick={() => select(id)} className="flex min-h-11 items-center justify-between gap-3 rounded-[var(--radius-md)] border border-[var(--line-strong)] px-4 text-left text-[14px] transition-colors hover:bg-white/6">
                <span>
                  {s.name} <span className="text-silver-500">· {s.place}</span>
                </span>
                <StatusGlyph status={assessments.get(id)!.overall} />
              </button>
            )
          })}
          <a href="#/app/analogs" className="mt-1 inline-flex min-h-11 items-center justify-center rounded-[var(--radius-md)] bg-amber px-4 font-medium text-ink-900 hover:bg-[#efb872]">Open Analog Explorer</a>
        </div>
      }
    />
  )
}

/* ─────────── Section header ─────────── */
export function SectionHead({ n, title, lede }: { n: string; title: string; lede?: ReactNode }) {
  return (
    <header className="mb-6 grid gap-2 md:grid-cols-[8rem_1fr] md:gap-6">
      <p className="mono pt-2 text-[12px] text-silver-400">{n}</p>
      <div className="max-w-2xl">
        <h2 className="font-display text-[26px] font-medium md:text-[30px]">{title}</h2>
        {lede && <p className="mt-2 text-[15px] leading-relaxed text-silver-400">{lede}</p>}
      </div>
    </header>
  )
}

/* ─────────── Data table ─────────── */
export function DataTable({ caption, head, rows, paper }: { caption?: string; head: string[]; rows: (string | number)[][]; paper?: boolean }) {
  return (
    <div className="scroll-thin overflow-x-auto">
      <table className="w-full min-w-[360px] border-collapse text-left text-[13px]">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} scope="col" className={cx('border-b border-[var(--line-strong)] px-2 py-2 font-medium', paper ? 'text-graphite-soft' : 'text-silver-400')}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-[var(--line)]">
              {r.map((c, j) => (j === 0 ? <th key={j} scope="row" className="mono px-2 py-2 font-normal">{c}</th> : <td key={j} className="mono px-2 py-2">{c}</td>))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ─────────── Chart frame: title, legend, accessible summary, source, table alternative ─────────── */
export interface LegendItem {
  label: string
  color: string
  dash?: string
  swatch?: 'line' | 'box'
}
export function Legend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-silver-300">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <svg width="22" height="10" aria-hidden>
            {i.swatch === 'box' ? <rect x="2" y="1" width="16" height="8" fill={i.color} /> : <line x1="0" x2="22" y1="5" y2="5" stroke={i.color} strokeWidth="2.2" strokeDasharray={i.dash} />}
          </svg>
          {i.label}
        </li>
      ))}
    </ul>
  )
}

export function ChartFrame({ title, summary, source, legend, table, children }: { title: string; summary: string; source: string; legend: LegendItem[]; table: { caption: string; head: string[]; rows: (string | number)[][] }; children: ReactNode }) {
  return (
    <figure className="min-w-0">
      <figcaption className="mb-3 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <h3 className="text-[15px] font-medium">{title}</h3>
        <Legend items={legend} />
      </figcaption>
      <div role="img" aria-label={summary} className="min-w-0 border-y border-[var(--line)] py-3">{children}</div>
      <div className="mt-2">
        <Note>Source: {source}</Note>
      </div>
      <Disclosure title={<span className="text-[13px] text-silver-300">View data table</span>}>
        <DataTable {...table} />
      </Disclosure>
    </figure>
  )
}
