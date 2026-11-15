import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { GLOSSARY, type TermId } from '../../lib/glossary'

/**
 * A glossary term: a focusable trigger whose definition is announced through aria-describedby and shown on hover,
 * and on tap, Enter or Space. Esc, blur or a press elsewhere closes it. Only for running text, never inside another control.
 */
export function Term({ id, children }: { id: TermId; children?: ReactNode }) {
  const g = GLOSSARY[id]
  const uid = useId()
  const btn = useRef<HTMLButtonElement>(null)
  const [at, setAt] = useState<{ left: number; y: number; up: boolean } | null>(null)

  const show = () => {
    const r = btn.current?.getBoundingClientRect()
    if (!r) return
    const w = Math.min(280, window.innerWidth - 16)
    const up = r.bottom + 150 > window.innerHeight && r.top > 160
    setAt({ left: Math.max(8, Math.min(r.left, window.innerWidth - w - 8)), y: up ? r.top - 6 : r.bottom + 6, up })
  }
  const hide = () => setAt(null)

  useEffect(() => {
    if (!at) return
    const key = (e: KeyboardEvent) => e.key === 'Escape' && hide()
    const press = (e: PointerEvent) => !btn.current?.contains(e.target as Node) && hide()
    document.addEventListener('keydown', key)
    document.addEventListener('pointerdown', press)
    window.addEventListener('scroll', hide, { passive: true, once: true })
    return () => { document.removeEventListener('keydown', key); document.removeEventListener('pointerdown', press); window.removeEventListener('scroll', hide) }
  }, [at])

  return (
    <>
      <button ref={btn} type="button" aria-describedby={uid} onClick={() => (at ? hide() : show())} onBlur={hide}
        onPointerEnter={(e) => e.pointerType === 'mouse' && show()} onPointerLeave={(e) => e.pointerType === 'mouse' && hide()}
        className="cursor-help rounded-[2px] underline decoration-dotted decoration-1 underline-offset-4">
        {children ?? g.term}
      </button>
      <span id={uid} className="sr-only">{g.def}</span>
      {at && createPortal(
        <span aria-hidden className="tw-term fixed z-[90] block rounded-[var(--radius-md)] border border-[var(--line-strong)] bg-ink-800 px-3 py-2.5 text-left text-[13px] leading-snug font-normal tracking-normal text-silver-200 normal-case shadow-[var(--shadow-pop)]"
          style={{ left: at.left, top: at.y, width: Math.min(280, window.innerWidth - 16), transform: at.up ? 'translateY(-100%)' : undefined }}>
          <span className="block font-medium text-paper">{g.term}</span>{g.def}
        </span>,
        document.body,
      )}
    </>
  )
}
