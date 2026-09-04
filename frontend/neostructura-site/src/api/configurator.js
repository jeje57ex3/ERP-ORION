export async function fetchConfiguratorOptions() {
  const res = await fetch('/api/v1/neostructura/configurateur/options/')
  if (!res.ok) throw new Error('Impossible de charger le configurateur.')
  return res.json()
}

export async function submitConfigurator(payload) {
  const res = await fetch('/api/v1/neostructura/configurateur/soumettre/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || "Une erreur est survenue. Réessayez plus tard.")
  return data
}
