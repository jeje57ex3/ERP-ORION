import { useState } from 'react'
import { checkGiftCard, applyGiftCard } from '../api/customer'

export default function GiftCardForm({ cartTotal, onApplied }) {
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [applied, setApplied] = useState(null)

  const handleApply = async () => {
    if (!code.trim()) return
    setLoading(true)
    setError('')
    try {
      const data = await applyGiftCard(code.trim().toUpperCase(), cartTotal)
      setApplied(data)
      onApplied?.(data)
    } catch (err) {
      setError(err?.response?.data?.error || 'Code invalide ou expiré.')
    } finally {
      setLoading(false)
    }
  }

  const handleRemove = () => {
    setApplied(null)
    setCode('')
    setError('')
    onApplied?.(null)
  }

  if (applied) {
    return (
      <div style={{
        padding: '14px 18px',
        background: 'rgba(192,168,130,0.05)',
        border: '1px solid rgba(192,168,130,0.2)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div>
          <p style={{ fontSize: 13, color: '#C0A882', fontWeight: 700, letterSpacing: '0.1em' }}>
            CARTE CADEAU {applied.code}
          </p>
          <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', marginTop: 3 }}>
            -{applied.applied_amount?.toFixed(2).replace('.', ',')} €
          </p>
        </div>
        <button
          onClick={handleRemove}
          style={{
            background: 'transparent', border: 'none',
            color: 'rgba(255,255,255,0.3)', cursor: 'pointer',
            fontSize: 11, letterSpacing: '0.12em',
          }}
        >
          RETIRER
        </button>
      </div>
    )
  }

  return (
    <div>
      <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', letterSpacing: '0.14em', marginBottom: 10 }}>
        CARTE CADEAU
      </p>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type="text"
          value={code}
          onChange={e => setCode(e.target.value.toUpperCase())}
          placeholder="CODE-XXXXXX"
          onKeyDown={e => e.key === 'Enter' && handleApply()}
          style={{
            flex: 1, padding: '11px 14px',
            background: '#000', border: '1px solid rgba(255,255,255,0.1)',
            color: '#fff', fontSize: 13, letterSpacing: '0.08em',
            outline: 'none',
          }}
        />
        <button
          onClick={handleApply}
          disabled={loading || !code.trim()}
          style={{
            padding: '11px 20px',
            background: 'transparent',
            border: '1px solid rgba(255,255,255,0.2)',
            color: loading ? 'rgba(255,255,255,0.3)' : '#fff',
            fontSize: 11, fontWeight: 700, letterSpacing: '0.14em',
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s', whiteSpace: 'nowrap',
          }}
          onMouseEnter={e => { if (!loading) e.currentTarget.style.borderColor = '#C0A882' }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)' }}
        >
          {loading ? '...' : 'APPLIQUER'}
        </button>
      </div>
      {error && (
        <p style={{ fontSize: 12, color: '#E07070', marginTop: 8 }}>{error}</p>
      )}
    </div>
  )
}
