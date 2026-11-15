import { useId } from 'react'
import type { TargetClass } from '../../lib/api/types'
import { CLASS_META, CLASS_ORDER } from '../../lib/rehearsal'

/*
 * How each classification is drawn. Colour is never the only signal: every class also has its own fill pattern and a
 * text label. "Insufficient coverage" is deliberately unlike shadow: shadow is a solid dark fill, an undecided sample is
 * an empty outlined cell with dots, so a reader cannot take "we could not tell" for "dark".
 */

export const CLASS_COLOR: Record<TargetClass, string> = {
  ILLUMINATED: '#e4a95b',
  TERRAIN_OBSTRUCTED: '#5d6fa3',
  SURFACE_FACING_AWAY: '#8a6f9e',
  INSUFFICIENT_COVERAGE: '#c5cad0',
  NO_DATA: '#e08d82',
  UNKNOWN: '#a9afb7',
}

/** SVG <defs> for the patterns. `prefix` makes the ids unique per chart. */
export function ClassPatterns({ prefix }: { prefix: string }) {
  return (
    <defs>
      <pattern id={`${prefix}-away`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="6" height="6" fill="#3b3550" />
        <line x1="0" y1="0" x2="0" y2="6" stroke={CLASS_COLOR.SURFACE_FACING_AWAY} strokeWidth="2.2" />
      </pattern>
      <pattern id={`${prefix}-gap`} width="6" height="6" patternUnits="userSpaceOnUse">
        <rect width="6" height="6" fill="transparent" />
        <circle cx="3" cy="3" r="1" fill={CLASS_COLOR.INSUFFICIENT_COVERAGE} />
      </pattern>
      <pattern id={`${prefix}-nodata`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
        <rect width="6" height="6" fill="transparent" />
        <line x1="0" y1="0" x2="0" y2="6" stroke={CLASS_COLOR.NO_DATA} strokeWidth="1.4" />
      </pattern>
    </defs>
  )
}

/** The fill and stroke of one cell. */
export function cellPaint(cls: TargetClass, prefix: string): { fill: string; stroke: string; strokeDasharray?: string } {
  switch (cls) {
    case 'ILLUMINATED': return { fill: CLASS_COLOR.ILLUMINATED, stroke: 'none' }
    case 'TERRAIN_OBSTRUCTED': return { fill: '#34406b', stroke: CLASS_COLOR.TERRAIN_OBSTRUCTED }
    case 'SURFACE_FACING_AWAY': return { fill: `url(#${prefix}-away)`, stroke: CLASS_COLOR.SURFACE_FACING_AWAY }
    case 'INSUFFICIENT_COVERAGE': return { fill: `url(#${prefix}-gap)`, stroke: CLASS_COLOR.INSUFFICIENT_COVERAGE, strokeDasharray: '3 2' }
    case 'NO_DATA': return { fill: `url(#${prefix}-nodata)`, stroke: CLASS_COLOR.NO_DATA, strokeDasharray: '3 2' }
    default: return { fill: `url(#${prefix}-gap)`, stroke: CLASS_COLOR.UNKNOWN, strokeDasharray: '2 2' }
  }
}

export function ClassSwatch({ cls, size = 18 }: { cls: TargetClass; size?: number }) {
  const id = useId().replace(/:/g, '')
  const p = cellPaint(cls, id)
  return (
    <svg width={size} height={size * 0.7} viewBox="0 0 18 12.6" aria-hidden className="shrink-0">
      <ClassPatterns prefix={id} />
      <rect x="0.75" y="0.75" width="16.5" height="11.1" rx="2" fill={p.fill} stroke={p.stroke} strokeWidth="1.5" strokeDasharray={p.strokeDasharray} />
    </svg>
  )
}

/** The legend: only the classes that occur, each with its meaning. */
export function ClassLegend({ present, counts }: { present: TargetClass[]; counts?: Partial<Record<TargetClass, number>> }) {
  const list = CLASS_ORDER.filter((c) => present.includes(c))
  return (
    <ul className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
      {list.map((c) => (
        <li key={c} className="flex items-start gap-2.5 text-[13px] leading-snug">
          <span className="mt-1"><ClassSwatch cls={c} /></span>
          <span className="min-w-0"><span className="font-medium text-paper">{CLASS_META[c].label}</span>{counts?.[c] !== undefined && <span className="mono text-silver-400"> · {counts[c]}</span>}<span className="block text-xs text-silver-400">{CLASS_META[c].meaning}</span></span>
        </li>
      ))}
    </ul>
  )
}
