import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { getRewards, useReward, getMe } from '../api/customer'
import RewardPointsCard from '../components/RewardPointsCard'
import LuxuryLoader from '../components/LuxuryLoader'

export default function Rewards() {
  const [loyalty, setLoyalty] = useState(null)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    getMe().then(me => {
      if (!me.authenticated) { navigate('/compte/connexion'); return null }
      return getRewards()
    }).then(d => {
      if (d) setLoyalty(d)
    }).catch(() => navigate('/compte/connexion'))
      .finally(() => setLoading(false))
  }, [navigate])

  const handleUseReward = async (reward_id) => {
    try {
      const res = await useReward(reward_id)
      setMsg(res.message || 'Récompense appliquée.')
      const updated = await getRewards()
      setLoyalty(updated)
      setTimeout(() => setMsg(''), 4000)
    } catch (err) {
      setMsg(err?.response?.data?.error || 'Erreur lors de l\'utilisation de la récompense.')
      setTimeout(() => setMsg(''), 4000)
    }
  }

  if (loading) return <LuxuryLoader />

  return (
    <div>
      <motion.h1
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        style={{
          fontFamily: 'Montserrat, sans-serif',
          fontSize: 28, fontWeight: 900, color: '#fff',
          letterSpacing: '0.04em', marginBottom: 36,
        }}
      >
        FIDÉLITÉ & RÉCOMPENSES
      </motion.h1>

      {msg && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            padding: '14px 20px',
            background: 'rgba(192,168,130,0.08)',
            border: '1px solid rgba(192,168,130,0.2)',
            color: '#C0A882', fontSize: 13,
            marginBottom: 24,
          }}
        >
          {msg}
        </motion.div>
      )}

      <RewardPointsCard loyalty={loyalty} onUseReward={handleUseReward} />

      <div style={{ marginTop: 32, padding: 24, background: '#111', border: '1px solid rgba(255,255,255,0.06)' }}>
        <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', letterSpacing: '0.12em', marginBottom: 10 }}>
          COMMENT GAGNER DES POINTS ?
        </p>
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {[
            '1€ dépensé = 1 point',
            'Parrainer un ami = 100 points bonus',
            'Atteindre le statut Silver = 50 points offerts',
            'Atteindre le statut Gold = 150 points offerts',
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
