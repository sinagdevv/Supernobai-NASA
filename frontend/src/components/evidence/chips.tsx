import { Ban, CircleAlert, CircleCheck, CircleDashed, CircleHelp, CircleX, FlaskConical, PencilRuler, ServerOff, ShieldCheck, TriangleAlert, type LucideIcon } from 'lucide-react'
import type { CriterionVerdict, OverallVerdict } from '../../lib/api/types'
import { EVIDENCE_LABEL, type EvidenceKind } from '../../lib/status'
import { CRITERION_META, OVERALL_META, type Tone } from '../../lib/suitability'
import { cx } from '../ui'
import { Term } from '../ui/Term'
import type { TermId } from '../../lib/glossary'

/** Verdicts and kinds whose label is a term worth defining in place. */
const VERDICT_TERM: Partial<Record<CriterionVerdict, TermId>> = { UNVERIFIED: 'unverified', INDETERMINATE: 'indeterminate' }
const KIND_TERM: Partial<Record<EvidenceKind, TermId>> = { insufficient: 'insufficient', computed: 'computed' }

/*
 * One look for each thing a result can be. Glyph, label and border carry the meaning, not colour alone.
 * Only a measured PASS (or "configured thresholds met") is green. A claim is amber and dashed, a gap is grey and dashed.
 */

const BASE = 'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium leading-5 whitespace-nowrap'

const TONE: Record<Tone, string> = {
  pass: 'border-ok/40 bg-ok/10 text-ok',
  fail: 'border-bad/40 bg-bad/10 text-bad',
  claim: 'border-dashed border-amber/60 bg-amber-soft text-amber',
  missing: 'border-dashed border-silver-500 bg-white/4 text-silver-300',
}

const ICON: Record<CriterionVerdict, LucideIcon> = { PASS: CircleCheck, FAIL: CircleX, UNVERIFIED: CircleHelp, INDETERMINATE: CircleDashed, NOT_ASSESSED: Ban }
const OVERALL_ICON: Record<OverallVerdict, LucideIcon> = { SUITABLE: CircleCheck, NOT_SUITABLE: CircleX, INDETERMINATE: CircleDashed, PARTIALLY_ASSESSED: CircleAlert }

export function VerdictChip({ verdict, className }: { verdict: CriterionVerdict; className?: string }) {
  const m = CRITERION_META[verdict], Icon = ICON[verdict]
  const t = VERDICT_TERM[verdict]
  return <span title={t ? undefined : m.meaning} className={cx(BASE, TONE[m.tone], className)}><Icon size={13} aria-hidden strokeWidth={2.2} />{t ? <Term id={t}>{m.label}</Term> : m.label}</span>
}

export function OverallChip({ verdict, className }: { verdict: OverallVerdict; className?: string }) {
  const m = OVERALL_META[verdict], Icon = OVERALL_ICON[verdict]
  return <span className={cx(BASE, 'text-[13px]', TONE[m.tone], className)}><Icon size={15} aria-hidden strokeWidth={2.2} />{verdict === 'INDETERMINATE' ? <Term id="indeterminate">{m.label}</Term> : m.label}</span>
}

const KIND_STYLE: Record<EvidenceKind, { Icon: LucideIcon; cls: string }> = {
  computed: { Icon: FlaskConical, cls: 'border-cyan/50 bg-cyan-soft text-cyan' },
  validated: { Icon: ShieldCheck, cls: 'border-ok/40 bg-ok/10 text-ok' },
  illustrative: { Icon: PencilRuler, cls: 'border-dashed border-silver-500 bg-white/4 text-silver-300' },
  insufficient: { Icon: TriangleAlert, cls: 'border-dashed border-amber/60 bg-amber-soft text-amber' },
  unavailable: { Icon: ServerOff, cls: 'border-bad/40 bg-bad/10 text-bad' },
}

/** What the result in front of you is: computed, illustrative, insufficient or unavailable. */
export function EvidenceChip({ kind, className }: { kind: EvidenceKind; className?: string }) {
  const { Icon, cls } = KIND_STYLE[kind]
  const t = KIND_TERM[kind]
  return <span title={t ? undefined : EVIDENCE_LABEL[kind].meaning} className={cx(BASE, cls, className)}><Icon size={13} aria-hidden strokeWidth={2.2} />{t ? <Term id={t}>{EVIDENCE_LABEL[kind].label}</Term> : EVIDENCE_LABEL[kind].label}</span>
}

/** Always shown beside a computed result: it has not been checked against observations. */
export function NotValidatedChip({ className }: { className?: string }) {
  return <span title="The engine reports observational_validation_status NOT_VALIDATED." className={cx(BASE, 'border-dashed border-silver-500 bg-white/4 text-silver-300', className)}><CircleDashed size={13} aria-hidden strokeWidth={2.2} />Not independently validated</span>
}
