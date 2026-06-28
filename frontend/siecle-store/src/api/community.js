import { apiGet, apiPost } from './apiClient'

export const getPosts       = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return apiGet(`/api/v1/siecle/community/posts/${qs ? '?' + qs : ''}`)
}
export const createPost     = (formData)    => {
  return fetch('/api/v1/siecle/community/posts/', {
    method: 'POST',
    credentials: 'include',
    body: formData,
  }).then(r => r.json())
}
export const likePost       = (id)          => apiPost(`/api/v1/siecle/community/posts/${id}/like/`)
export const deletePost     = (id)          => apiPost(`/api/v1/siecle/community/posts/${id}/delete/`)
