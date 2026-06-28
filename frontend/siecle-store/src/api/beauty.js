import { apiGet, apiPost } from './apiClient'

export const submitBeautyQuiz = (answers)  => apiPost('/api/v1/siecle/beauty/quiz/', answers)
export const submitShadeFinder = (data)    => apiPost('/api/v1/siecle/beauty/shade-finder/', data)
export const getMakeupProducts = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return apiGet(`/api/v1/siecle/products/?category=maquillage${qs ? '&' + qs : ''}`)
}
export const getBeautyProfile = ()         => apiGet('/api/v1/siecle/customer/beauty-profile/')
