import api from './client'

const AUTH = '/siecle/auth'
const CUS  = '/siecle/customer'

export const register = (data)      => api.post(`${AUTH}/register/`, data).then(r => r.data)
export const login    = (data)      => api.post(`${AUTH}/login/`, data).then(r => r.data)
export const logout   = ()          => api.post(`${AUTH}/logout/`).then(r => r.data)
export const getMe    = ()          => api.get(`${AUTH}/me/`).then(r => r.data)

export const getAccount  = ()       => api.get(`${CUS}/account/`).then(r => r.data)
export const getOrders   = ()       => api.get(`${CUS}/orders/`).then(r => r.data)
export const getRewards  = ()       => api.get(`${CUS}/rewards/`).then(r => r.data)
export const useReward   = (reward_id) => api.post(`${CUS}/rewards/use/`, { reward_id }).then(r => r.data)
export const getAffiliate = ()      => api.get(`${CUS}/affiliate/`).then(r => r.data)
export const createAffiliateCode = () => api.post(`${CUS}/affiliate/create-code/`).then(r => r.data)

export const checkGiftCard   = (code)              => api.get(`/siecle/gift-card/${code}/`).then(r => r.data)
export const applyGiftCard   = (code, cart_total)  => api.post('/siecle/cart/apply-gift-card/', { code, cart_total }).then(r => r.data)
export const applyReward     = (reward_id, cart_total) => api.post('/siecle/cart/apply-reward/', { reward_id, cart_total }).then(r => r.data)

// Stocke le token dans axios après login/register
export const setAuthToken = (token) => {
  if (token) {
    api.defaults.headers.common['Authorization'] = `Token ${token}`
    localStorage.setItem('siecle_auth_token', token)
  } else {
    delete api.defaults.headers.common['Authorization']
    localStorage.removeItem('siecle_auth_token')
  }
}

export const initAuthFromStorage = () => {
  const token = localStorage.getItem('siecle_auth_token')
  if (token) setAuthToken(token)
}
