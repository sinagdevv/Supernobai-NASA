import { RotateCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from './ui'

const SETUP_DOCS = 'https://github.com/sinagdevv/Supernobai-NASA#getting-started'

/**
 * The state of a measured or computed panel when its numbers cannot be had: the service is down, still being looked for, or the dataset is not on the machine
 * running it. It says what is missing and what the panel would show, offers a retry, and keeps developer setup behind a disclosure.
 * `preview` is a real image rendered once by Layer 3 from the stored Jezero region: a look at the dataset, never a measurement.
 */
export function ServiceUnavailable({ kind, title, heading: H = 'h3', context, onRetry, setup, preview }: { kind: 'offline' | 'checking' | 'dataset'; title: string; /** The level that follows the heading above it on the page, so levels never skip. */ heading?: 'h2' | 'h3' | 'h4'; context: ReactNode; onRetry?: () => void; setup?: string; preview?: { src: string; alt: string; caption: string } }) {
  const checking = kind === 'checking'
  return (
    <div role="status" className="grid gap-6 rounded-[var(--radius-lg)] border border-[var(--line-strong)] bg-ink-850 p-5 md:grid-cols-[minmax(0,1fr)_minmax(0,15rem)] md:p-6">
      <div className="min-w-0">
        <p className="mono flex items-center gap-2 text-xs tracking-[0.04em] text-silver-300 uppercase">
          <i aria-hidden className={`h-1.5 w-1.5 rounded-full ${checking ? 'bg-silver-500' : 'bg-bad'}`} />
          {checking ? 'Checking service' : kind === 'dataset' ? 'Dataset not retrieved' : 'Service unavailable'}
        </p>
        <H className="font-display mt-3 text-[24px] leading-[1.1] md:text-[28px]">{title}</H>
        <p className="mt-3 max-w-[34rem] text-[15px] leading-[1.55] text-silver-300">{context}</p>
        {onRetry && !checking && <Button className="mt-5" onClick={onRetry}><RotateCw size={15} aria-hidden /> Try again</Button>}
        <details className="mt-5 text-[13px] text-silver-400">
          <summary className="min-h-11 cursor-pointer py-2 text-silver-300">For developers</summary>
          <p className="max-w-[34rem]">The measurements and calculations (terrain, solar geometry, suitability) come from the TERRAWINDOW service, which the hosted frontend cannot reach unless it is deployed alongside it. Nothing is shown in place of a result it could not give. Setup and the service command are in the <a className="text-cyan underline underline-offset-2 hover:text-paper" href={SETUP_DOCS} target="_blank" rel="noreferrer noopener">README<span className="sr-only"> (opens in new tab)</span></a>.</p>
          {setup && <p className="mono mt-2 text-xs break-words text-silver-500">{setup}</p>}
        </details>
      </div>
      {preview && (
        <figure className="min-w-0 self-start">
          <img src={preview.src} alt={preview.alt} width={270} height={258} loading="lazy" className="block h-auto w-full rounded-[var(--radius-md)] border border-[var(--line)]" />
          <figcaption className="mt-2 text-xs leading-snug text-silver-400">{preview.caption}</figcaption>
        </figure>
      )}
    </div>
  )
}

export const JEZERO_PREVIEW = {
  src: '/mars/jezero-elevation.png',
  alt: 'Elevation of the Jezero region of Mars from MOLA topography, rendered once from the stored dataset',
  caption: 'Dataset preview, rendered from the stored MOLA region. A look at the data, not a measurement.',
}
