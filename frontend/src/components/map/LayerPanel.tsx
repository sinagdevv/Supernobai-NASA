import type { Status } from '../../data/types'
import { STATUS_LABEL } from '../../lib/assess'
import { useApp, type BaseMap } from '../../lib/store'
import { cx, Segmented, StatusGlyph, Toggle } from '../ui'
import { BASE_INFO, BASE_KEYS } from './mapStyle'

const LEGEND: Status[] = ['potential', 'not-suitable', 'not-assessed']

function Ring({ className }: { className: string }) {
  return <span aria-hidden className={cx('inline-block h-3.5 w-3.5 rounded-full border-2 bg-ink-900', className)} />
}

/** Body of the Layers popover: basemap, relief, and a one-line-per-item legend. */
export function LayerPopover() {
  const { baseMap, setBaseMap, relief, setRelief } = useApp()
  return (
    <div className="w-[236px]">
      <Segmented<BaseMap> label="Basemap" value={baseMap} onChange={setBaseMap} options={BASE_KEYS.map((b) => ({ value: b, label: BASE_INFO[b].label }))} />
      <Toggle label="Terrain relief" hint="Optional context, from zoom 3" checked={relief} onChange={setRelief} />
      <ul className="mt-1 space-y-1.5 border-t border-[var(--line)] pt-3 text-[12px] text-silver-300">
        {LEGEND.map((s) => (
          <li key={s} className="flex items-center gap-2"><StatusGlyph status={s} size={15} />{STATUS_LABEL[s]}</li>
        ))}
        <li className="flex items-center gap-2"><Ring className="border-amber" />Selected</li>
        <li className="flex items-center gap-2"><Ring className="border-cyan" />In comparison (up to 3)</li>
      </ul>
      <p className="mt-2.5 text-[12px] leading-snug text-silver-400">Prototype example sites, not survey results. Status covers screened criteria only.</p>
    </div>
  )
}
