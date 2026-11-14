import { useId, useState } from 'react'
import { fmtMin, type Segment } from '../../lib/solar'

// Drawn thumb is 20px wide, matching the native thumb, so it lines up with pointer position (10px track inset).
const DAY = 1439

/**
 * The day as a timeline. A native range input sits invisibly on top (keyboard, screen readers, drag and
 * click-to-seek all come free); the track, qualifying-window spans and thumb are drawn underneath.
 * The thumb follows input 1:1 — it only eases when `smooth` is set (a chip or window jump, not a drag).
 */
export function TimeScrubber({ minute, onChange, segments, tz, smooth, label = 'Local time' }: { minute: number; onChange: (m: number) => void; segments: Segment[]; tz: string; smooth: boolean; label?: string }) {
  const id = useId()
  const [ring, setRing] = useState(false) // keyboard focus only (:focus-visible)
  const frac = minute / DAY
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-[13px] font-medium text-silver-200">{label}</label>
        <output htmlFor={id} className="mono text-[14px] text-amber">{fmtMin(minute)} {tz}</output>
      </div>
      <div className="relative h-11">
        <input id={id} type="range" min={0} max={DAY} step={5} value={minute} aria-valuetext={`${fmtMin(minute)} ${tz}`} onChange={(e) => onChange(+e.target.value)} onFocus={(e) => setRing(e.currentTarget.matches(':focus-visible'))} onBlur={() => setRing(false)} className="absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0" />
        <div aria-hidden className="absolute inset-x-[10px] top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-ink-600">
          {segments.map((s) => (
            <span key={s.startMin} className="absolute inset-y-0 rounded-full bg-amber" style={{ left: `${(s.startMin / DAY) * 100}%`, width: `max(6px, ${((s.endMin - s.startMin) / DAY) * 100}%)` }} />
          ))}
        </div>
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute inset-x-[10px] top-1/2 h-0">
          <div className="h-0 w-full" style={{ transform: `translateX(${frac * 100}%)`, transition: smooth ? 'transform 220ms var(--ease-out)' : 'none' }}>
            <span className="absolute top-0 left-0 block h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink-900 bg-paper" style={{ boxShadow: ring ? '0 0 0 2px var(--color-amber)' : '0 0 0 1px var(--color-silver-400)' }} />
          </div>
          </div>
        </div>
      </div>
      <div aria-hidden className="relative -mt-1 h-4 text-[12px] text-silver-500">
        {[0, 6, 12, 18, 24].map((h) => (
          <span key={h} className="mono absolute top-0" style={{ left: `calc(10px + (100% - 20px) * ${h / 24})`, transform: `translateX(-${h === 0 ? 0 : h === 24 ? 100 : 50}%)` }}>
            {String(h).padStart(2, '0')}
          </span>
        ))}
      </div>
    </div>
  )
}
