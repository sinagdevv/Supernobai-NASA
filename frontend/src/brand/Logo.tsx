import { useId } from 'react'
import { MARK_CHANNEL, MARK_H, MARK_LOWER, MARK_UPPER, MARK_VIEWBOX, MARK_W, WORDMARK_GLYPHS, WORDMARK_WIDTH } from './paths'

/*
 * TERRAWINDOW identity — construction
 * - The mark is two terrain-profile ribbons held parallel: the lunar reference above, an Earth analog below.
 *   Between them a constant-width channel is the window: the specific conditions in which the two correspond.
 * - Every segment of the profile runs at dx/dy = 0.5; the ribbons share one thickness and the channel one gap.
 *   The ends are cut vertically, so the profile reads as a section of a longer horizon.
 * - Colour carries meaning, never decoration: silver = lunar reference, cyan = Earth reference, amber = the window.
 *   In monochrome the channel is left as pure negative space.
 * - The wordmark uses the same logic: monoline strokes, flat cuts at cap height and baseline, diagonals on a steeper 0.4 slope (for legibility at nav size),
 *   chamfered bowls (R, D, O).
 * Colours come from --mark-a/b/c (see index.css) so the mark is correct on dark and paper surfaces.
 */

type MarkProps = { className?: string; mono?: boolean; title?: string }

export function MarkShapes({ mono }: { mono?: boolean }) {
  return (
    <>
      <path d={MARK_UPPER} fill={mono ? 'currentColor' : 'var(--mark-a)'} />
      {!mono && <path d={MARK_CHANNEL} fill="var(--mark-b)" />}
      <path d={MARK_LOWER} fill={mono ? 'currentColor' : 'var(--mark-c)'} />
    </>
  )
}

export function LogoMark({ className, mono, title = 'TERRAWINDOW' }: MarkProps) {
  return (
    <svg viewBox={MARK_VIEWBOX} className={className} role="img" aria-label={title} focusable="false">
      <MarkShapes mono={mono} />
    </svg>
  )
}

const Glyphs = ({ clip }: { clip: string }) => (
  <g
    fill="none"
    stroke="currentColor"
    strokeWidth="1.7"
    strokeLinejoin="miter"
    strokeMiterlimit="12"
    clipPath={`url(#${clip})`}
    dangerouslySetInnerHTML={{ __html: WORDMARK_GLYPHS }}
  />
)

export function Wordmark({ className }: { className?: string }) {
  const id = useId()
  return (
    <svg viewBox={`0 0 ${WORDMARK_WIDTH} 10`} className={className} role="img" aria-label="TERRAWINDOW" focusable="false">
      <defs>
        <clipPath id={id}>
          <rect x="-2" y="0" width={WORDMARK_WIDTH + 4} height="10" />
        </clipPath>
      </defs>
      <Glyphs clip={id} />
    </svg>
  )
}

const LOCK_SCALE = 0.36
const LOCK_H = 20.6
const LOCK_GAP = 8
export const LOCKUP_W = +(MARK_W * LOCK_SCALE + LOCK_GAP + WORDMARK_WIDTH).toFixed(1)

/** Horizontal lockup: symbol + wordmark. Text inherits `color`; height is set by the caller. */
export function Lockup({ className, mono, target }: { className?: string; mono?: boolean; target?: boolean }) {
  const id = useId()
  const markY = (LOCK_H - MARK_H * LOCK_SCALE) / 2 + 6 * LOCK_SCALE
  return (
    <svg viewBox={`0 0 ${LOCKUP_W} ${LOCK_H}`} className={className} role="img" aria-label="TERRAWINDOW" focusable="false">
      <defs>
        <clipPath id={id}>
          <rect x="-2" y="0" width={WORDMARK_WIDTH + 4} height="10" />
        </clipPath>
      </defs>
      {/* Invisible box the intro docks into (see Intro.tsx) */}
      {target && <rect data-nav-mark x={0} y={(LOCK_H - MARK_H * LOCK_SCALE) / 2} width={MARK_W * LOCK_SCALE} height={MARK_H * LOCK_SCALE} fill="none" pointerEvents="none" />}
      <g transform={`translate(0 ${markY}) scale(${LOCK_SCALE})`}>
        <MarkShapes mono={mono} />
      </g>
      <g transform={`translate(${MARK_W * LOCK_SCALE + LOCK_GAP} ${(LOCK_H - 10) / 2})`}>
        <Glyphs clip={id} />
      </g>
    </svg>
  )
}
