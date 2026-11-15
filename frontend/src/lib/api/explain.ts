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
    case 'rate_limited':
    case 'unavailable':
      return { text: e.message }
    case 'rehearsal_rejected':
      return { text: `The solar-geometry engine rejected this request: ${e.message}` }
    case 'layer4_unavailable':
      return { text: 'The solar-geometry engine (Layer 4) is not available on this server, so no rehearsal window can be computed.' }
    case 'invalid_request':
      return { text: `The request was not accepted: ${e.message}` }
    case 'unreachable':
      return { text: 'The service stopped answering.' }
    default:
      return { text: e.message }
  }
}
