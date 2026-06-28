import { apiGet } from './apiClient'

export const search           = (q, universe) => {
  const params = new URLSearchParams({ q })
  if (universe) params.set('universe', universe)
  return apiGet(`/api/v1/siecle/search/?${params}`)
}
export const getSuggestions   = (q) => apiGet(`/api/v1/siecle/search/suggestions/?q=${encodeURIComponent(q)}`)
export const getCategories    = ()  => apiGet('/api/v1/siecle/categories/')
