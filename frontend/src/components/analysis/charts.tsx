import { useReducedMotion } from 'motion/react'
import { useId, useMemo } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ROUGH_SCALES, SLOPE_BINS, SLOPE_EDGES } from '../../data/mission'
import type { LunarRegion, Mission, Site } from '../../data/types'
import { resolvable, rmsAt } from '../../lib/assess'
import { profile } from '../../lib/terrain'
import { C, ChartFrame, tickStyle, tooltipStyle } from './shared'

const axisLabel = (value: string, angle?: number) => ({ value, fill: C.axis, fontSize: 12, angle, position: angle ? ('insideLeft' as const) : ('insideBottom' as const), offset: angle ? 14 : -4, style: { textAnchor: 'middle' as const } })
const show = (v: unknown) => (typeof v === 'number' ? v.toFixed(2) : String(v))

/* ─────────── Elevation profile ─────────── */
export function ElevationChart({ region, site }: { region: LunarRegion; site: Site }) {
  const reduce = useReducedMotion()
  const data = useMemo(() => {
    const m = profile('moon', region.seed, 224, 128, 3)
    const e = profile('earth', site.seed, 224, 128, 3)
    return m.map((p, i) => ({ x: p.x, moon: p.z, earth: e[i].z }))
  }, [region.seed, site.seed])
  const range = (k: 'moon' | 'earth') => {
    const v = data.map((d) => d[k])
    return Math.max(...v) - Math.min(...v)
  }
  return (
    <ChartFrame
      title="Elevation along a west–east transect"
      summary={`Relative elevation profile over ${data[data.length - 1].x} metres. Lunar reference relief ${range('moon').toFixed(1)} m; Earth candidate relief ${range('earth').toFixed(1)} m. Illustrative synthetic terrain.`}
      source="synthetic terrain rows, vertical relief un-exaggerated, 10 m/px — illustrative, not LOLA or Earth DEM data"
      legend={[{ label: 'Lunar reference', color: C.moon }, { label: 'Earth candidate', color: C.earth, dash: '5 4' }]}
      table={{ caption: 'Relative elevation by distance', head: ['Distance (m)', 'Lunar ref. (m)', 'Earth cand. (m)'], rows: data.filter((_, i) => i % 4 === 0).map((d) => [d.x, d.moon, d.earth]) }}
    >
      <ResponsiveContainer width="100%" height={240} minWidth={0}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 18, left: 6 }}>
          <CartesianGrid stroke={C.grid} vertical={false} />
          <XAxis dataKey="x" type="number" domain={[0, 'dataMax']} tick={tickStyle} tickFormatter={(v) => `${v}`} label={axisLabel('Distance along transect (m)')} stroke={C.grid} />
          <YAxis tick={tickStyle} label={axisLabel('Relative elevation (m)', -90)} width={52} stroke={C.grid} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${show(v)} m`} labelFormatter={(l) => `${l} m along transect`} />
          <Line type="monotone" dataKey="moon" name="Lunar reference" stroke={C.moon} strokeWidth={2} dot={false} isAnimationActive={!reduce} animationDuration={600} />
          <Line type="monotone" dataKey="earth" name="Earth candidate" stroke={C.earth} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={!reduce} animationDuration={600} />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

/* ─────────── Slope distribution ─────────── */
export function SlopeChart({ region, site, mission }: { region: LunarRegion; site: Site; mission: Mission }) {
  const reduce = useReducedMotion()
  const data = SLOPE_BINS.map((b, i) => ({ bin: b, lo: SLOPE_EDGES[i], moon: region.slopeHist[i], earth: site.slopeHist[i] }))
  return (
    <ChartFrame
      title="Slope distribution"
      summary={`Share of mapped area by slope bin. Bins at or above the ${mission.slopeMax}° screening limit are shown faded. Illustrative fixtures.`}
      source="illustrative slope histograms — lunar: LOLA 5 m product assumed; Earth: per-site DEM assumption"
      legend={[{ label: 'Lunar reference', color: C.moon, swatch: 'box' }, { label: 'Earth candidate', color: C.earth, swatch: 'box' }, { label: `Faded: ≥ ${mission.slopeMax}° limit`, color: '#5a626d', swatch: 'box' }]}
      table={{ caption: 'Percent of area by slope bin', head: ['Slope bin', 'Lunar ref. (%)', 'Earth cand. (%)'], rows: data.map((d) => [d.bin, d.moon, d.earth]) }}
    >
      <ResponsiveContainer width="100%" height={240} minWidth={0}>
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 18, left: 6 }} barCategoryGap="22%">
          <CartesianGrid stroke={C.grid} vertical={false} />
          <XAxis dataKey="bin" tick={tickStyle} label={axisLabel('Slope (degrees)')} stroke={C.grid} />
          <YAxis tick={tickStyle} unit="%" label={axisLabel('Share of area (%)', -90)} width={52} stroke={C.grid} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.05)' }} formatter={(v) => `${show(v)} %`} />
          <Bar dataKey="moon" name="Lunar reference" fill={C.moon} isAnimationActive={!reduce} animationDuration={500}>
            {data.map((d) => <Cell key={d.bin} fillOpacity={d.lo >= mission.slopeMax ? 0.35 : 1} />)}
          </Bar>
          <Bar dataKey="earth" name="Earth candidate" fill={C.earth} isAnimationActive={!reduce} animationDuration={500}>
            {data.map((d) => <Cell key={d.bin} fillOpacity={d.lo >= mission.slopeMax ? 0.35 : 1} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  )
}

/* ─────────── Roughness by analysis scale ─────────── */
export function RoughnessChart({ region, site, mission }: { region: LunarRegion; site: Site; mission: Mission }) {
  const reduce = useReducedMotion()
  const hatch = useId().replace(/:/g, '')
  const coarse = Math.max(region.dem.resM, site.dem.resM)
  const data = ROUGH_SCALES.map((L) => {
    const mOk = resolvable(region.dem.resM, L), eOk = resolvable(site.dem.resM, L)
    const m = rmsAt(region.rough, L), e = rmsAt(site.rough, L)
    return { L, m, e, mOk, eOk, mR: mOk ? m : null, eR: eOk ? e : null, mU: mOk ? null : m, eU: eOk ? null : e }
  })
  // connect dashed to first resolved point
  const firstM = data.find((d) => d.mOk), firstE = data.find((d) => d.eOk)
  if (firstM) firstM.mU = firstM.m
  if (firstE) firstE.eU = firstE.e
  const unresolvedEarth = data.filter((d) => !d.eOk).map((d) => d.L)
  const unresolvedMoon = data.filter((d) => !d.mOk).map((d) => d.L)
  return (
    <ChartFrame
      title="Roughness by analysis scale"
      summary={`RMS height deviation versus baseline length on a log axis. Dashed segments and the hatched band mark baselines below twice the grid spacing, which the data cannot resolve. Mission limit ${mission.roughMax} m at ${mission.roughBaseline} m.`}
      source={`illustrative power-law fixtures; lunar grid ${region.dem.resM} m, Earth grid ${site.dem.resM} m`}
      legend={[
        { label: 'Lunar reference', color: C.moon },
        { label: 'Earth candidate', color: C.earth },
        { label: 'Unresolved (dashed)', color: C.axis, dash: '3 3' },
        { label: `Limit ${mission.roughMax} m`, color: C.ref, dash: '6 3' },
      ]}
      table={{
        caption: 'RMS height deviation by baseline',
        head: ['Baseline (m)', 'Lunar ref. RMS (m)', 'Earth cand. RMS (m)'],
        rows: data.map((d) => [d.L, d.mOk ? d.m.toFixed(2) : `${d.m.toFixed(2)} — unresolved`, d.eOk ? d.e.toFixed(2) : `${d.e.toFixed(2)} — unresolved`]),
      }}
    >
      <ResponsiveContainer width="100%" height={260} minWidth={0}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 18, left: 6 }}>
          <defs>
            <pattern id={hatch} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="6" stroke={C.axis} strokeWidth="1.4" strokeOpacity="0.55" />
            </pattern>
          </defs>
          <CartesianGrid stroke={C.grid} vertical={false} />
          {coarse * 2 > ROUGH_SCALES[0] && <ReferenceArea x1={ROUGH_SCALES[0]} x2={Math.min(coarse * 2, 200)} fill={`url(#${hatch})`} stroke="none" ifOverflow="hidden" />}
          <XAxis dataKey="L" type="number" scale="log" domain={[5, 200]} ticks={[...ROUGH_SCALES]} allowDataOverflow tick={tickStyle} label={axisLabel('Analysis baseline (m, log scale)')} stroke={C.grid} />
          <YAxis tick={tickStyle} domain={[0, (max: number) => Math.max(max, mission.roughMax * 1.2)]} tickFormatter={(v) => (+v).toFixed(1)} label={axisLabel('RMS height deviation (m)', -90)} width={52} stroke={C.grid} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${show(v)} m`} labelFormatter={(l) => `${l} m baseline`} />
          <ReferenceLine y={mission.roughMax} stroke={C.ref} strokeDasharray="6 3" strokeWidth={1.5} />
          <ReferenceLine x={mission.roughBaseline} stroke={C.ref} strokeOpacity={0.6} />
          <Line dataKey="mR" name="Lunar reference" stroke={C.moon} strokeWidth={2} dot={{ r: 3 }} connectNulls={false} isAnimationActive={!reduce} animationDuration={500} />
          <Line dataKey="mU" name="Lunar (unresolved)" stroke={C.moon} strokeWidth={1.5} strokeDasharray="3 3" dot={{ r: 3, fill: C.bg }} connectNulls={false} isAnimationActive={false} legendType="none" />
          <Line dataKey="eR" name="Earth candidate" stroke={C.earth} strokeWidth={2} dot={{ r: 3 }} connectNulls={false} isAnimationActive={!reduce} animationDuration={500} />
          <Line dataKey="eU" name="Earth (unresolved)" stroke={C.earth} strokeWidth={1.5} strokeDasharray="3 3" dot={{ r: 3, fill: C.bg }} connectNulls={false} isAnimationActive={false} legendType="none" />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 px-1 text-[12px] leading-relaxed text-silver-400">
        {unresolvedEarth.length || unresolvedMoon.length ? (
          <>
            Below 2× grid spacing, a dataset cannot resolve the baseline (hollow markers, dashed lines).{' '}
            {unresolvedEarth.length > 0 && <>Earth {site.dem.resM} m grid: baselines {unresolvedEarth.join(', ')} m. </>}
            {unresolvedMoon.length > 0 && <>Lunar {region.dem.resM} m grid: baselines {unresolvedMoon.join(', ')} m. </>}
          </>
        ) : (
          'Both grids resolve every plotted baseline.'
        )}
      </p>
    </ChartFrame>
  )
}

/* ─────────── Dataset resolution, same ground area ─────────── */
const AREA = 150
function Grid({ res, label, color }: { res: number; label: string; color: string }) {
  const id = useId().replace(/:/g, '')
  const cells = Math.round((AREA / res) ** 2)
  const sw = Math.min(0.5, res * 0.06)
  return (
    <figure className="min-w-0">
      <svg viewBox={`-2 -2 ${AREA + 4} ${AREA + 16}`} className="block w-full" aria-hidden>
        <defs>
          <pattern id={id} width={res} height={res} patternUnits="userSpaceOnUse">
            <path d={`M${res} 0H0V${res}`} fill="none" stroke={color} strokeWidth={sw} strokeOpacity="0.85" />
          </pattern>
        </defs>
        <rect width={AREA} height={AREA} fill="#1b2027" />
        <rect width={AREA} height={AREA} fill={`url(#${id})`} />
        <rect x={AREA / 2 - res / 2} y={AREA / 2 - res / 2} width={res} height={res} fill={C.ref} fillOpacity="0.85" />
        <rect width={AREA} height={AREA} fill="none" stroke={color} strokeWidth="0.6" />
        <path d={`M0 ${AREA + 6}H${AREA}M0 ${AREA + 3}V${AREA + 9}M${AREA} ${AREA + 3}V${AREA + 9}`} stroke={C.axis} strokeWidth="0.5" fill="none" />
        <text x={AREA / 2} y={AREA + 15} textAnchor="middle" fontSize="7" fill={C.axis} fontFamily="monospace">150 m</text>
      </svg>
      <figcaption className="mt-2">
        <p className="text-[13px] font-medium" style={{ color }}>{label}</p>
        <p className="mono text-[12px] text-silver-300">{res} m cells · {cells.toLocaleString()} cell{cells === 1 ? '' : 's'} in this area</p>
      </figcaption>
    </figure>
  )
}
export function ResolutionGrid({ region, site }: { region: LunarRegion; site: Site }) {
  return (
    <div>
      <div className="grid max-w-3xl grid-cols-2 gap-5 sm:gap-10" role="img" aria-label={`The same 150 by 150 metre ground area sampled by a ${region.dem.resM} metre lunar grid (${Math.round((AREA / region.dem.resM) ** 2)} cells) and a ${site.dem.resM} metre Earth grid (${Math.round((AREA / site.dem.resM) ** 2)} cells). The amber square is one cell.`}>
        <Grid res={region.dem.resM} label="Lunar reference grid" color={C.moon} />
        <Grid res={site.dem.resM} label="Earth candidate grid" color={C.earth} />
      </div>
      <p className="mt-3 max-w-xl text-[12px] leading-relaxed text-silver-400">Amber = one elevation sample. Grids of different spacing are <strong className="font-medium text-paper">not equivalent detail</strong>: hazards under about 2 cells are invisible. Fixture values.</p>
    </div>
  )
}
