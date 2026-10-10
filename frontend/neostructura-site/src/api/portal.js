const TOKEN_KEY = 'neostructura:client_token'

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}

function setToken(token) {
  try { localStorage.setItem(TOKEN_KEY, token) } catch {}
}

function clearToken() {
  try { localStorage.removeItem(TOKEN_KEY) } catch {}
}

async function authedFetch(url, options = {}) {
  const token = getToken()
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Token ${token}`
  const res = await fetch(url, { ...options, headers })
  if (res.status === 401) clearToken()
  return res
}

export async function portalLogin(email, password) {
  const res = await fetch('/api/v1/neostructura/portail/connexion/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Connexion impossible.')
  setToken(data.token)
  return data.account
}

export async function portalLogout() {
  try {
    await authedFetch('/api/v1/neostructura/portail/deconnexion/', { method: 'POST' })
  } finally {
    clearToken()
  }
}

export async function portalFetchMe() {
  const res = await authedFetch('/api/v1/neostructura/portail/moi/')
  if (!res.ok) return null
  return res.json()
}

export async function portalFetchDashboard() {
  const res = await authedFetch('/api/v1/neostructura/portail/tableau-de-bord/')
  if (!res.ok) throw new Error("Impossible de charger le tableau de bord.")
  return res.json()
}
