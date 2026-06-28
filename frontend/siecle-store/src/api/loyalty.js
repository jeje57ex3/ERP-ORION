import { apiGet, apiPost } from './apiClient'

export const getLoyalty      = ()          => apiGet('/api/v1/siecle/loyalty/')
export const getLoyaltyTiers = ()          => apiGet('/api/v1/siecle/loyalty/tiers/')
export const getLoyaltyHistory = ()        => apiGet('/api/v1/siecle/loyalty/history/')
export const redeemPoints    = (points)    => apiPost('/api/v1/siecle/loyalty/redeem/', { points })
export const getMissions     = ()          => apiGet('/api/v1/siecle/loyalty/missions/')
export const completeMission = (id)        => apiPost(`/api/v1/siecle/loyalty/missions/${id}/complete/`)
