const BASE = import.meta.env.VITE_API_BASE || ''

function getCsrf() {
  return document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=')[1] || ''
}

async function request(method, url, data) {
  const opts = {
    method,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrf() },
  }
  if (data !== undefined) opts.body = JSON.stringify(data)
  const res = await fetch(`${BASE}${url}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw Object.assign(new Error(err.detail || 'Erreur réseau'), { status: res.status, data: err })
  }
  if (res.status === 204) return null
  return res.json()
}

export const apiGet    = (url)         => request('GET',    url)
export const apiPost   = (url, data)   => request('POST',   url, data)
export const apiPut    = (url, data)   => request('PUT',    url, data)
export const apiPatch  = (url, data)   => request('PATCH',  url, data)
export const apiDelete = (url)         => request('DELETE', url)
