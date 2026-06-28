import { apiGet, apiPost, apiDelete } from './apiClient'

export const getCart        = ()           => apiGet('/api/v1/siecle/cart/')
export const addToCart      = (item)       => apiPost('/api/v1/siecle/cart/add/', item)
export const removeFromCart = (itemId)     => apiDelete(`/api/v1/siecle/cart/remove/${itemId}/`)
export const updateQty      = (itemId, q)  => apiPost('/api/v1/siecle/cart/update/', { item_id: itemId, quantity: q })
export const clearCart      = ()           => apiDelete('/api/v1/siecle/cart/clear/')
export const applyPromo     = (code)       => apiPost('/api/v1/siecle/cart/promo/', { code })
export const addPack        = (packId)     => apiPost('/api/v1/siecle/cart/add-pack/', { pack_id: packId })
export const addLook        = (lookId)     => apiPost('/api/v1/siecle/cart/add-look/', { look_id: lookId })
export const createCheckout = (payload)    => apiPost('/api/v1/siecle/create-checkout-session/', payload)
