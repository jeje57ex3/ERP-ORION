import { apiGet, apiPost } from './apiClient'

export const getLooks    = ()      => apiGet('/api/v1/siecle/looks/')
export const getLook     = (id)    => apiGet(`/api/v1/siecle/looks/${id}/`)
export const createLook  = (data)  => apiPost('/api/v1/siecle/looks/', data)
export const saveLook    = (data)  => apiPost('/api/v1/siecle/customer/saved-looks/', data)
