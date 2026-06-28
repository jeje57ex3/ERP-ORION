import { apiGet, apiPost } from './apiClient'

export const getClothingProducts = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return apiGet(`/api/v1/siecle/products/?category=vetements${qs ? '&' + qs : ''}`)
}
export const getSizeProfile  = ()          => apiGet('/api/v1/siecle/customer/size-profile/')
export const saveSizeProfile = (data)      => apiPost('/api/v1/siecle/customer/size-profile/', data)
export const getProductVideo = (productId) => apiGet(`/api/v1/siecle/products/${productId}/video/`)
