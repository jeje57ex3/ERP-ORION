export async function sendContactMessage(payload) {
  const res = await fetch('/api/v1/neostructura/contact/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.error || "Une erreur est survenue. Réessayez plus tard.")
  }
  return data
}
