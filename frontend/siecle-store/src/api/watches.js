import { apiGet, apiPost } from './apiClient'

export const getWatches           = (params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return apiGet(`/api/v1/siecle/products/?category=montres${qs ? '&' + qs : ''}`)
}
export const getWatch             = (id)           => apiGet(`/api/v1/siecle/products/${id}/`)
export const getWatchCertificate  = (id)           => apiGet(`/api/v1/siecle/watches/certificate/${id}/`)
export const saveConfiguration    = (data)         => apiPost('/api/v1/siecle/customer/watch-configurations/', data)
export const getConfigurations    = ()             => apiGet('/api/v1/siecle/customer/watch-configurations/')

// ── Atelier SIÈCLE ────────────────────────────────────────────────────────
export async function addCustomWatchToCart({ brand_key, base_product_slug, configuration, price, harmony_score }) {
  const res = await fetch('/api/v1/siecle/cart/add-custom-watch/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ brand_key, base_product_slug, configuration, price, harmony_score }),
  })
  if (!res.ok) throw new Error("Impossible d'ajouter la montre au panier.")
  return res.json()
}

export async function saveWatchAtelier({ name, configuration, base_price, options_price, total_price, harmony_score, story }) {
  const res = await fetch('/api/v1/siecle/watches/configs/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ name, configuration, base_price, options_price, total_price, harmony_score, story }),
  })
  if (!res.ok) throw new Error('Sauvegarde impossible.')
  return res.json()
}

export async function loadWatchAtelier(shareToken) {
  const res = await fetch(`/api/v1/siecle/watches/configs/?token=${shareToken}`, { credentials: 'include' })
  if (!res.ok) throw new Error('Configuration introuvable.')
  return res.json()
}
