import { apiGet, apiPost } from './apiClient'

export const getGiftCardDesigns = ()      => apiGet('/api/v1/siecle/giftcards/designs/')
export const createGiftCard     = (data)  => apiPost('/api/v1/siecle/giftcards/create/', data)
export const getGiftCard        = (code)  => apiGet(`/api/v1/siecle/giftcards/${code}/`)
export const redeemGiftCard     = (code)  => apiPost('/api/v1/siecle/giftcards/redeem/', { code })
