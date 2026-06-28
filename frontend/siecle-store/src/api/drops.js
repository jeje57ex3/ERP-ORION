import { apiGet, apiPost } from './apiClient'

export const getDrops        = ()       => apiGet('/api/v1/siecle/drops/')
export const getDrop         = (slug)   => apiGet(`/api/v1/siecle/drops/${slug}/`)
export const registerForDrop = (dropId) => apiPost(`/api/v1/siecle/drops/${dropId}/register/`)
