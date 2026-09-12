const BASE = '/api/v1/neostructura/configurateur'

async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Une erreur est survenue. Réessayez plus tard.')
  return data
}

export async function fetchDomains() {
  const res = await fetch(`${BASE}/domaines/`)
  if (!res.ok) throw new Error('Impossible de charger le configurateur.')
  const data = await res.json()
  return data.domains
}

export async function fetchServices(domainCode) {
  const res = await fetch(`${BASE}/domaines/${domainCode}/services/`)
  if (!res.ok) throw new Error('Impossible de charger les prestations.')
  const data = await res.json()
  return data.services
}

export async function fetchQuestions(serviceCode, answers) {
  const data = await postJSON(`${BASE}/services/${serviceCode}/questions/`, { answers })
  return data.questions
}

export async function estimateLive(payload) {
  return postJSON(`${BASE}/estimer/`, payload)
}

export async function submitConfigurator(payload) {
  return postJSON(`${BASE}/soumettre/`, payload)
}

export async function uploadPhotos(reference, files) {
  const formData = new FormData()
  for (const f of files) formData.append('photos', f)
  const res = await fetch(`${BASE}/${reference}/photos/`, { method: 'POST', body: formData })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || "Impossible d'envoyer les photos.")
  return data
}
