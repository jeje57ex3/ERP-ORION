import { apiGet, apiPost } from './apiClient'

export const getAffiliateStats   = ()       => apiGet('/api/v1/siecle/affiliate/stats/')
export const getAffiliateLinks   = ()       => apiGet('/api/v1/siecle/affiliate/links/')
export const createAffiliateLink = (data)   => apiPost('/api/v1/siecle/affiliate/links/', data)
export const getAffiliatePayouts = ()       => apiGet('/api/v1/siecle/affiliate/payouts/')
export const requestPayout       = (amount) => apiPost('/api/v1/siecle/affiliate/payouts/request/', { amount })
