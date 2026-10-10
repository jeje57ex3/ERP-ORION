const BASE = '/api/v1/neostructura/configurateur'
const LANG_STORAGE_KEY = 'neostructura_lang'

// Lit la langue courante directement depuis le stockage utilisé par
// LanguageContext (src/i18n/LanguageContext.jsx) plutôt que de la faire
// passer en prop à travers toute la chaîne de composants — le contenu
// dynamique du configurateur (domaines, prestations, questions, message
// de sécurité) doit suivre la même langue que le reste du site.
function getCurrentLang() {
  try {
    return window.localStorage?.getItem(LANG_STORAGE_KEY) || 'fr'
  } catch {
    return 'fr'
  }
}

async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lang: getCurrentLang(), ...payload }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || 'Une erreur est survenue. Réessayez plus tard.')
  return data
}

export async function fetchDomains() {
  const res = await fetch(`${BASE}/domaines/?lang=${getCurrentLang()}`)
  if (!res.ok) throw new Error('Impossible de charger le configurateur.')
  const data = await res.json()
  return data.domains
}

export async function fetchServices(domainCode) {
  const res = await fetch(`${BASE}/domaines/${domainCode}/services/?lang=${getCurrentLang()}`)
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

export async function startSession() {
  return postJSON(`${BASE}/session/`, {})
}

export async function fetchSession(sessionKey) {
  const res = await fetch(`${BASE}/session/${sessionKey}/?lang=${getCurrentLang()}`)
  if (!res.ok) return null
  return res.json()
}

export async function updateSession(sessionKey, payload) {
  return postJSON(`${BASE}/session/${sessionKey}/`, payload)
}

export async function addSessionLot(sessionKey, payload) {
  return postJSON(`${BASE}/session/${sessionKey}/lots/`, payload)
}

export async function submitConfiguratorProject(payload) {
  return postJSON(`${BASE}/soumettre-projet/`, payload)
}

export async function uploadPhotos(reference, files) {
  const formData = new FormData()
  for (const f of files) formData.append('photos', f)
  const res = await fetch(`${BASE}/${reference}/photos/`, { method: 'POST', body: formData })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || "Impossible d'envoyer les photos.")
  return data
}
