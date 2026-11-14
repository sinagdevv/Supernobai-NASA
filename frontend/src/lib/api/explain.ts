import type { ApiError } from './client'

/** One plain-language reading of a service failure, shared by every panel that calls the service. `setup` is the fix the service suggested, if any. */
export function explain(e: ApiError): { text: string; setup?: string } {
  const d = (e.details ?? {}) as { setup?: string }
  const setup = typeof d.setup === 'string' ? d.setup : undefined
  switch (e.code) {
    case 'source_unavailable':
      return { text: 'This dataset is listed, but its raster is not on this machine. Fetch it with Layer 2, then try again.', setup }
    case 'source_unreadable':
      return { text: 'The raster file exists but cannot be read. It may be truncated or corrupt: fetch it again.', setup }
    case 'dataset_not_validated':
      return { text: 'Layer 2 marked this dataset as failing validation, so it is not used.', setup }
    case 'scale_not_supported':
    case 'patch_too_small':
      return { text: `${e.message} The requested scale or patch size is not supported by this dataset.` }
    case 'patch_too_large':
      return { text: `${e.message} Choose a larger patch size.` }
    case 'unreachable':
      return { text: 'The Layer 3 service stopped answering.' }
    default:
      return { text: e.message }
  }
}
