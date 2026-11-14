/** Compass showing rover heading (arrow) and the light direction (sun or lamp marker). */
export function RoverCompass({ heading, lightAz, lightLabel, dim, smooth }: { heading: number; lightAz: number; lightLabel: string; dim?: boolean; smooth?: boolean }) {
  const R = 78
  const spin = (deg: number) => ({ transform: `rotate(${deg}deg)`, transformOrigin: '0 0', transition: smooth ? 'transform 220ms var(--ease-out)' : 'none' }) as const
  return (
    <svg viewBox="0 0 200 200" role="img" aria-label={`Compass: rover heading ${Math.round(heading)}°, ${lightLabel.toLowerCase()} azimuth ${Math.round(lightAz)}°`} className="mx-auto block h-auto w-full max-w-[200px]">
      <g transform="translate(100 100)">
        <circle r={R} fill="var(--color-ink-900)" stroke="var(--line-strong)" />
        <circle r={R - 22} fill="none" stroke="var(--line)" strokeDasharray="2 4" />
        {Array.from({ length: 36 }, (_, i) => (
          <line key={i} x1="0" x2="0" y1={-R} y2={-R + (i % 3 === 0 ? 8 : 4)} stroke="var(--color-silver-500)" strokeWidth="1" transform={`rotate(${i * 10})`} />
        ))}
        {[
          ['N', 0, -R - 9],
          ['E', R + 10, 4],
          ['S', 0, R + 15],
          ['W', -R - 10, 4],
        ].map(([t, tx, ty]) => (
          <text key={t as string} x={tx as number} y={ty as number} textAnchor="middle" className="mono" fontSize="12" fill="var(--color-silver-300)">
            {t}
          </text>
        ))}
        {/* light direction */}
        <g style={spin(lightAz)} opacity={dim ? 0.4 : 1}>
          <line x1="0" y1="-14" x2="0" y2={-R + 10} stroke="var(--color-amber)" strokeDasharray="3 3" />
          <circle cy={-R} r="7" fill="var(--color-amber)" stroke="var(--color-ink-900)" strokeWidth="2" />
        </g>
        {/* rover heading */}
        <g style={spin(heading)}>
          <path d="M0 -50 L11 -20 L0 -27 L-11 -20 Z" fill="var(--color-paper)" stroke="var(--color-ink-900)" strokeWidth="1.5" strokeLinejoin="round" />
          <rect x="-8" y="-18" width="16" height="30" rx="3" fill="var(--color-ink-700)" stroke="var(--color-silver-400)" />
        </g>
      </g>
    </svg>
  )
}
