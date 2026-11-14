import { motion } from 'motion/react'
import { Check, Copy, Download, Printer } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { Lockup } from '../../brand/Logo'
import { Pips, evidenceOf } from '../../components/analysis/figures'
import { buildReport, toMarkdown, toSummary, type Row } from '../../components/analysis/report'
import { DataTable, NoSite, Note } from '../../components/analysis/shared'
import { StatusBadge, cx } from '../../components/ui'
import { GeoDot, ProfileThumb, SunArc } from '../../components/viz'
import { DEMO_HORIZON_DAYS } from '../../data/mission'
import { DISCLAIMER, SOURCES } from '../../data/sources'
import { siteById } from '../../data/sites'
import { STATUS_LABEL, regionById, resolvable, rmsAt, shareBelow } from '../../lib/assess'
import { useApp } from '../../lib/store'

const reveal = {
  initial: { opacity: 0, y: 8 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '0px 0px -8% 0px' },
  transition: { duration: 0.24, ease: [0.23, 1, 0.32, 1] as const },
}

/** Sections reveal on scroll; print CSS forces them visible so an unscrolled page still prints completely. */
function Section({ n, title, children }: { n: string; title: string; children: ReactNode }) {
  return (
    <motion.section {...reveal} className="print-avoid-break border-t border-[var(--line-strong)] py-8 print:opacity-100! print:transform-none! md:grid md:grid-cols-[3.5rem_minmax(0,1fr)] md:gap-x-4">
      <span className="mono text-[13px] text-graphite-soft md:pt-2.5">{n}</span>
      <div className="min-w-0">
        <h2 className="font-display mb-6 text-[26px] md:text-[30px]">{title}</h2>
        {children}
      </div>
    </motion.section>
  )
}

function KV({ rows }: { rows: Row[] }) {
  return (
    <dl className="text-[14px]">
      {rows.map(([k, v]) => (
        <div key={k + v} className="grid grid-cols-[7.5rem_1fr] gap-x-4 border-b border-[var(--line)] py-2">
          <dt className="text-[13px] text-graphite-soft">{k}</dt>
          <dd className="[overflow-wrap:anywhere]">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

/** Dark plate for graphics drawn in the app's dark palette; colours are kept when printing. */
const Plate = ({ children, className }: { children: ReactNode; className?: string }) => (
  <div className={cx('rounded-[var(--radius-sm)] bg-ink-900 p-4 text-paper [-webkit-print-color-adjust:exact] [print-color-adjust:exact]', className)}>{children}</div>
)

export default function Dossier() {
  const { selectedId, mission, assessments, date } = useApp()
  const site = siteById(selectedId)
  const [note, setNote] = useState('')
  const report = useMemo(() => (site ? buildReport(site, mission, assessments.get(site.id)!, regionById(mission.regionId), date) : null), [site, mission, assessments, date])
  if (!site || !report) return <NoSite what="research dossier" />

  const a = report.assessment
  const region = report.region
  const shareE = shareBelow(site.slopeHist, mission.slopeMax), shareM = shareBelow(region.slopeHist, mission.slopeMax)
  const rE = rmsAt(site.rough, mission.roughBaseline), rM = rmsAt(region.rough, mission.roughBaseline)
  const okR = resolvable(site.dem.resM, mission.roughBaseline)
  const findings: [string, string][] = [
    ['Terrain', `${shareE.toFixed(0)}% of the Earth area is ≤ ${mission.slopeMax}° (lunar ${shareM.toFixed(0)}%); roughness at ${mission.roughBaseline} m is ${okR ? `${rE.toFixed(2)} m RMS vs ${rM.toFixed(2)} m lunar, limit ${mission.roughMax.toFixed(1)} m` : `not resolvable on a ${site.dem.resM} m grid`}.`],
    ['Sunlight', `${a.qualifyingDays} of ${DEMO_HORIZON_DAYS} days have the sun in ${mission.elMin}–${mission.elMax}° for ≥ ${mission.minDuration} min (natural light, illustrative).`],
    ['Evidence', `${a.assessedCount} of ${a.totalCount} criteria assessed. ${a.criteria.filter((c) => c.status === 'not-assessed' && c.id !== 'roughness' && c.id !== 'resolution').map((c) => c.label.toLowerCase()).join(' and ') || 'No further gaps'} not yet assessed.`],
  ]
  const month = +date.slice(5, 7) - 1
  const risk = { L: 'Low', M: 'Moderate', H: 'High' }[site.seasonalRisk[month] as 'L' | 'M' | 'H']

  const say = (t: string) => {
    setNote(t)
    window.setTimeout(() => setNote(''), 3000)
  }
  const download = () => {
    const url = URL.createObjectURL(new Blob([toMarkdown(report)], { type: 'text/markdown;charset=utf-8' }))
    const el = document.createElement('a')
    el.href = url
    el.download = 'terrawindow-dossier.md'
    el.click()
    URL.revokeObjectURL(url)
    say('Markdown downloaded')
  }
  const copy = async () => {
    const text = toSummary(report)
    try {
      await navigator.clipboard.writeText(text)
      say('Summary copied')
    } catch {
      // Clipboard API unavailable (insecure context / permissions): fall back to a hidden textarea.
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand('copy')
      ta.remove()
      say(ok ? 'Summary copied' : 'Copy failed — use Download Markdown')
    }
  }
  const btn = 'inline-flex min-h-11 items-center gap-2 rounded-[var(--radius-md)] px-3.5 text-[13px] font-medium transition-[background-color,transform] duration-[var(--duration-fast)] active:scale-[0.97] md:min-h-9'

  return (
    <div className="bg-ink-900 pb-10 md:px-6 md:py-10 print:bg-white print:p-0">
      <div className="no-print mx-auto mb-4 flex max-w-[860px] flex-wrap items-center gap-2 px-4 pt-6 md:px-0 md:pt-0">
        <button type="button" onClick={() => window.print()} className={cx(btn, 'bg-amber text-ink-900 hover:bg-[#efb872]')}><Printer size={15} aria-hidden />Print / Save as PDF</button>
        <button type="button" onClick={download} className={cx(btn, 'border border-[var(--line-strong)] text-paper hover:bg-white/8')}><Download size={15} aria-hidden />Download Markdown</button>
        <button type="button" onClick={copy} className={cx(btn, 'border border-[var(--line-strong)] text-paper hover:bg-white/8')}><Copy size={15} aria-hidden />Copy summary</button>
        <span role="status" aria-live="polite" className="mono flex min-h-5 items-center gap-1 text-[12px] text-ok">{note && <><Check size={13} aria-hidden />{note}</>}</span>
      </div>

      <article className="paper print-page mx-auto max-w-[860px] px-5 py-8 shadow-paper sm:px-10 md:rounded-[var(--radius-md)] md:px-14 md:py-12" aria-label="Research dossier">
        {/* Header + summary */}
        <motion.header {...reveal} className="pb-10 print:opacity-100! print:transform-none!">
          <div className="flex items-center justify-between gap-4">
            <Lockup className="h-6 text-graphite" />
            <p className="mono text-[12px] text-graphite-soft">Prototype 0.1 · demo snapshot</p>
          </div>
          <p className="eyebrow mt-12">Research dossier</p>
          <h1 className="font-display mt-3 max-w-[18ch] text-[40px] md:text-[54px]">Prototype preliminary assessment</h1>
          <p className="font-display mt-4 text-[20px] text-graphite-soft">{report.title}</p>

          <div className="mt-8 grid gap-x-10 gap-y-6 border-y border-[var(--line-strong)] py-6 md:grid-cols-[minmax(0,13rem)_1fr]">
            <div>
              <StatusBadge status={a.overall} paper />
              <p className="mt-2 text-[12px] leading-snug text-graphite-soft">screened criteria only · {a.assessedCount} of {a.totalCount} assessed · no single similarity score</p>
            </div>
            <dl className="space-y-3 text-[15px] leading-snug">
              {findings.map(([k, v]) => (
                <div key={k} className="grid grid-cols-[5.5rem_1fr] gap-x-3"><dt className="text-[13px] font-medium text-graphite-soft">{k}</dt><dd className="max-w-[60ch]">{v}</dd></div>
              ))}
            </dl>
          </div>
          <div role="note" className="mt-6 border-l-2 border-amber-deep py-1 pl-4 text-[14px] leading-relaxed">
            <p className="font-semibold text-amber-deep">Not an official NASA qualification.</p>
            <p className="mt-1 max-w-[68ch] text-graphite-soft">{DISCLAIMER}</p>
          </div>
        </motion.header>

        <Section n="01" title="Mission and lunar reference">
          <div className="grid gap-x-10 gap-y-6 md:grid-cols-2"><KV rows={report.mission} /><KV rows={report.lunar} /></div>
        </Section>

        <Section n="02" title="Earth candidate">
          <div className="grid gap-x-10 gap-y-6 md:grid-cols-[1fr_minmax(0,15rem)]">
            <div>
              <KV rows={report.earth.filter(([k]) => !['Description', 'Heritage'].includes(k))} />
              <p className="mt-4 max-w-[62ch] text-[15px] leading-relaxed">{site.summary}</p>
              <p className="mt-3 text-[13px] leading-relaxed text-graphite-soft"><span className="font-medium text-graphite">{report.monthLabel.split(' ')[0]} weather limitation: {risk}</span> (qualitative, illustrative). {site.limitations.join(' ')}</p>
            </div>
            <figure>
              <Plate className="p-0"><GeoDot lat={site.lat} lon={site.lon} w={240} h={120} className="block w-full" /></Plate>
              <figcaption className="mt-1.5"><Note paper>Schematic locator, not a basemap.</Note></figcaption>
            </figure>
          </div>
        </Section>

        <Section n="03" title="Terrain comparison">
          <figure className="print-avoid-break">
            <Plate className="space-y-3">
              {([['moon', 'Lunar reference', region.seed, region.dem.resM], ['earth', 'Earth candidate', site.seed, site.dem.resM]] as const).map(([k, label, seed, res]) => (
                <div key={k} className="grid items-center gap-x-4 gap-y-1 sm:grid-cols-[9rem_1fr]">
                  <div><p className={cx('text-[13px] font-medium', k === 'earth' ? 'text-cyan' : 'text-silver-200')}>{label}</p><p className="mono text-[12px] text-silver-400">{res} m cells</p></div>
                  <ProfileThumb kind={k} seed={seed} sunEl={3} w={640} h={48} className="h-12 w-full" label={`${label} terrain profile lit by a 3° sun (schematic)`} />
                </div>
              ))}
            </Plate>
            <figcaption className="mt-1.5"><Note paper>Schematic profiles, sun 3°, shaded stretches dimmed. Not survey data. 5 m and 30 m grids are not equivalent detail.</Note></figcaption>
          </figure>
          <div className="print-avoid-break mt-5"><DataTable paper caption="Terrain screening figures" head={['Metric', 'Lunar reference', 'Earth candidate']} rows={report.terrain} /></div>
        </Section>

        <Section n="04" title={`Rehearsal windows · ${report.monthLabel}`}>
          <figure className="print-avoid-break">
            <Plate><SunArc site={site} date={date} lo={mission.elMin} hi={mission.elMax} minDur={mission.minDuration} w={640} h={96} className="h-auto w-full" /></Plate>
            <figcaption className="mt-1.5"><Note paper>{date} · sun elevation over the local day; amber = inside {mission.elMin}–{mission.elMax}° for ≥ {mission.minDuration} min. Natural light only.</Note></figcaption>
          </figure>
          {report.windows.length ? (
            <div className="print-avoid-break mt-5"><DataTable paper caption="Candidate natural-light windows" head={['Date', 'Local time', 'Phase', 'Elevation', 'Azimuth', 'Duration']} rows={report.windows.slice(0, 8).map((w) => [w.date, w.time, w.phase, w.el, w.az, w.dur])} /></div>
          ) : (
            <p className="mt-5 text-[15px]">No day this month has the sun in the {mission.elMin}–{mission.elMax}° band for at least {mission.minDuration} min.</p>
          )}
          <p className="mt-3 max-w-[66ch] text-[13px] leading-relaxed text-graphite-soft">Local standard time ({site.tzLabel}). Simplified flat-horizon model, illustrative, not a verified prediction. Artificial lighting is a different source and is not covered.</p>
        </Section>

        <Section n="05" title="Criterion assessment">
          <div className="scroll-thin print-avoid-break overflow-x-auto">
            <table className="w-full min-w-[540px] border-collapse text-left text-[14px]">
              <caption className="sr-only">Assessment by criterion</caption>
              <thead>
                <tr className="text-[13px] text-graphite-soft">
                  {['Criterion', 'Category', 'Evidence', 'Basis'].map((h) => <th key={h} scope="col" className="border-b border-[var(--line-strong)] py-2 pr-4 font-medium">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {a.criteria.map((c) => (
                  <tr key={c.id} className="border-b border-[var(--line)] align-top">
                    <th scope="row" className="py-3 pr-4 font-medium">{c.label}</th>
                    <td className="py-3 pr-4"><StatusBadge status={c.status} paper compact label={c.id === 'environment' ? 'Not reproducible' : STATUS_LABEL[c.status]} /></td>
                    <td className="py-3 pr-4">{c.id === 'environment' ? <span className="text-[12px] text-graphite-soft">n/a</span> : <Pips level={evidenceOf(c)} paper />}</td>
                    <td className="py-3 text-[13px] text-graphite-soft">{c.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section n="06" title="Limits and gaps">
          <div className="grid gap-x-10 gap-y-6 md:grid-cols-2">
            <div><h3 className="mb-2 text-[13px] font-medium text-graphite-soft">What this site cannot reproduce</h3><KV rows={report.gaps.filter(([k]) => /gravity|vacuum|radiation|thermal/i.test(k))} /></div>
            <div>
              <h3 className="mb-2 text-[13px] font-medium text-graphite-soft">Still to measure</h3>
              <ul className="divide-y divide-[var(--line)] border-y border-[var(--line)] text-[14px]">
                {report.missing.map((m) => <li key={m} className="flex gap-3 py-2"><i aria-hidden className="mt-1.5 h-3 w-3 shrink-0 rounded-[2px] border border-dashed border-graphite-soft" /><span>{m}</span></li>)}
              </ul>
            </div>
          </div>
        </Section>

        <Section n="07" title="Data provenance">
          <ul className="max-w-[68ch] space-y-1.5 text-[14px]">
            {SOURCES.map((s) => (
              <li key={s.id}><a href={s.url} target="_blank" rel="noreferrer noopener" className="font-medium text-cyan-deep underline underline-offset-2">{s.name}</a><span className="text-graphite-soft"> — {s.role}</span></li>
            ))}
          </ul>
          <div className="mt-4"><KV rows={report.provenance.slice(SOURCES.length)} /></div>
          <p className="mt-3 text-[12px] text-graphite-soft">Listing a resource does not imply endorsement by, or affiliation with, any agency.</p>
        </Section>

        <Section n="08" title="Field-verification steps">
          <ol className="max-w-[68ch] space-y-2.5 text-[15px]">
            {report.steps.map((s, i) => (
              <li key={i} className="grid grid-cols-[2rem_1fr] gap-2"><span className="mono text-[13px] text-amber-deep">{i + 1}.</span><span>{s}</span></li>
            ))}
          </ol>
        </Section>

        <footer className="mt-2 border-t border-[var(--line-strong)] pt-5">
          <p className="mono text-[12px] leading-relaxed text-graphite-soft">TERRAWINDOW prototype preliminary assessment · illustrative demonstration data · not an official NASA qualification · no endorsement implied.</p>
        </footer>
      </article>
    </div>
  )
}
