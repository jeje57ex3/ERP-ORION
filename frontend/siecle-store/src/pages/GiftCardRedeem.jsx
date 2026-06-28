import { useState } from 'react'
import { motion } from 'framer-motion'
import { checkGiftCard } from '../api/customer'

export default function GiftCardRedeem() {
  const [code, setCode] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleCheck = async () => {
    if (!code.trim()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const data = await checkGiftCard(code.trim().toUpperCase())
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.error || 'Code invalide ou expiré.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          fontFamily: 'Montserrat, sans-serif',
          fontSize: 28, fontWeight: 900, color: '#fff',
          letterSpacing: '0.04em', marginBottom: 12,
        }}
      >
        CARTES CADEAUX
      </motion.h1>
      <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14, lineHeight: 1.7, marginBottom: 36 }}>
        Vérifiez le solde d'une carte cadeau ou utilisez-la lors de votre prochain achat.
      </p>

      {/* Check form */}
      <div style={{
        background: '#111', border: '1px solid rgba(255,255,255,0.06)',
        padding: 32, marginBottom: 24,
      }}>
        <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11, letterSpacing: '0.15em', marginBottom: 16 }}>
          VÉRIFIER UN CODE
        </p>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            type="text"
            value={code}
            onChange={e => setCode(e.target.value.toUpperCase())}
            placeholder="CODE-XXXXXX"
            onKeyDown={e => e.key === 'Enter' && handleCheck()}
            style={{
              flex: 1, padding: '13px 16px',
              background: '#000', border: '1px solid rgba(255,255,255,0.1)',
              color: '#fff', fontSize: 14, letterSpacing: '0.08em',
              outline: 'none',
            }}
          />
          <button
            onClick={handleCheck}
            disabled={loading || !code.trim()}
            style={{
              padding: '13px 24px',
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.2)',
              color: '#fff', fontSize: 11, fontWeight: 700,
              letterSpacing: '0.14em', cursor: 'pointer',
              transition: 'all 0.2s', whiteSpace: 'nowrap',
              opacity: loading ? 0.5 : 1,
            }}
            onMouseEnter={e => { if (!loading) { e.currentTarget.style.borderColor = '#C0A882'; e.currentTarget.style.color = '#C0A882' } }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)'; e.currentTarget.style.color = '#fff' }}
          >
            {loading ? '...' : 'VÉRIFIER'}
          </button>
        </div>

        {error && (
          <p style={{ fontSize: 13, color: '#E07070', marginTop: 12 }}>{error}</p>
        )}
      </div>

      {/* Result */}
      {result && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            background: result.valid ? 'rgba(192,168,130,0.04)' : 'rgba(255,100,100,0.04)',
            border: `1px solid ${result.valid ? 'rgba(192,168,130,0.2)' : 'rgba(255,100,100,0.2)'}`,
            padding: 28,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <p style={{ fontSize: 13, fontWeight: 700, color: '#fff', letterSpacing: '0.1em' }}>
              {code}
            </p>
            <span style={{
              padding: '4px 12px',
              fontSize: 10, fontWeight: 700, letterSpacing: '0.14em',
              color: result.valid ? '#C0A882' : '#E07070',
              border: `1px solid ${result.valid ? 'rgba(192,168,130,0.3)' : 'rgba(224,112,112,0.3)'}`,
            }}>
              {result.valid ? 'VALIDE' : 'INVALIDE'}
            </span>
          </div>

          {result.valid && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
              <div>
                <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', letterSpacing: '0.14em', marginBottom: 6 }}>
                  SOLDE DISPONIBLE
                </p>
                <p style={{ fontSize: 28, fontWeight: 900, color: '#C0A882', fontFamily: 'Montserrat, sans-serif' }}>
                  {result.remaining_amount?.toFixed(2).replace('.', ',')} €
                </p>
              </div>
              {result.expires_at && (
                <div>
                  <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', letterSpacing: '0.14em', marginBottom: 6 }}>
                    EXPIRATION
                  </p>
                  <p style={{ fontSize: 16, fontWeight: 600, color: '#fff' }}>
                    {new Date(result.expires_at).toLocaleDateString('fr-FR')}
                  </p>
                </div>
              )}
            </div>
          )}

          {!result.valid && (
            <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.45)', lineHeight: 1.7 }}>
              {result.reason || 'Cette carte cadeau n\'est pas utilisable.'}
            </p>
          )}
        </motion.div>
      )}

      <div style={{ marginTop: 32, padding: 24, background: '#111', border: '1px solid rgba(255,255,255,0.06)' }}>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', letterSpacing: '0.12em', marginBottom: 10 }}>
          COMMENT UTILISER UNE CARTE CADEAU ?
        </p>
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[
            'Ajoutez vos articles au panier',
            'Lors du récapitulatif, saisissez votre code carte cadeau',
            'Le montant est automatiquement déduit de votre total',
            'Si votre achat est inférieur au solde, le reste est conservé',
          ].map(item => (
            <li key={item} style={{
              fontSize: 13, color: 'rgba(255,255,255,0.45)',
              paddingLeft: 16, position: 'relative',
            }}>
              <span style={{ position: 'absolute', left: 0, color: '#C0A882' }}>—</span>
              {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
