/** Plain-language definitions for the terms the interface uses. Each says what the term means here, and no more. */
export const GLOSSARY = {
  provenance: { term: 'Provenance', def: 'Where the data came from: the dataset, its citation, native pixel size, how it was resampled and which engine version produced the result.' },
  roughness: { term: 'Roughness', def: 'How much ground height varies over a stated distance, here as RMS height at a baseline. It depends on the baseline and on the grid resolution, so it is only comparable at the same scale.' },
  coverage: { term: 'Evidence coverage', def: 'The share of the analysed area that has valid elevation data. Cells without data are not counted as flat, shadowed or lit.' },
  indeterminate: { term: 'Indeterminate', def: 'The evidence is not enough to give a pass or fail. It is a statement about the data, not a result about the site.' },
  unverified: { term: 'Unverified claim', def: 'A value supplied by a person or catalogue rather than measured by the engine. It is shown, but it is never counted as a pass.' },
  insufficient: { term: 'Insufficient coverage', def: 'Too little valid terrain data around the target to decide whether the sun is blocked. This is neither shadow nor light.' },
  computed: { term: 'Computed vs validated', def: 'Computed means the engine returned the result for this request. Validated would mean it was checked against observations; nothing here is.' },
  scale: { term: 'Analysis scale', def: 'The grid spacing a statistic is computed at. Slopes and roughness change with scale, so two sites are compared at one shared scale.' },
} as const

export type TermId = keyof typeof GLOSSARY
