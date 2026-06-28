import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { getOrders, getMe } from '../api/customer'
import LuxuryLoader from '../components/LuxuryLoader'

const STATUS_LABELS = {
  pending: 'En attente',
  paid: 'Payée',
  processing: 'En traitement',
  shipped: 'Expédiée',
  delivered: 'Livrée',
  cancelled: 'Annulée',
}

export default function CustomerOrders() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    getMe().then(me => {
      if (!me.authenticated) { navigate('/compte/connexion'); return null }
      return getOrders()
    }).then(d => {
      if (d) setOrders(d.orders || [])
    }).catch(() => navigate('/compte/connexion'))
      .finally(() => setLoading(false))
  }, [navigate])

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
        MES COMMANDES
      </motion.h1>

      {orders.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <p style={{ color: 'rgba(255,255,255,0.35)', fontSize: 14, lineHeight: 1.7, marginBottom: 24 }}>
            Vous n'avez pas encore passé de commande.
          </p>
          <Link to="/boutique" style={{
            display: 'inline-block', padding: '13px 28px',
            border: '1px solid rgba(255,255,255,0.2)', color: '#fff',
            fontSize: 11, fontWeight: 700, letterSpacing: '0.14em',
          }}>
            DÉCOUVRIR LA BOUTIQUE
          </Link>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {orders.map((order, i) => (
            <motion.div
              key={order.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              style={{
                background: '#111', border: '1px solid rgba(255,255,255,0.06)',
                padding: 24,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                <div>
                  <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)', letterSpacing: '0.12em', marginBottom: 4 }}>
                    COMMANDE #{order.id}
                  </p>
                  <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.25)' }}>
                    {order.created_at ? new Date(order.created_at).toLocaleDateString('fr-FR', {
                      year: 'numeric', month: 'long', day: 'numeric',
                    }) : ''}
                  </p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{
                    display: 'inline-block', padding: '4px 10px', marginBottom: 6,
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.12em',
                    color: order.status === 'paid' || order.status === 'delivered' ? '#C0A882' : 'rgba(255,255,255,0.4)',
                    border: `1px solid ${order.status === 'paid' || order.status === 'delivered' ? 'rgba(192,168,130,0.3)' : 'rgba(255,255,255,0.08)'}`,
                  }}>
                    {STATUS_LABELS[order.status] || order.status}
                  </span>
                  <p style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>
                    {parseFloat(order.total_amount || 0).toFixed(2).replace('.', ',')} €
                  </p>
                </div>
              </div>

              {order.items && order.items.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {order.items.map((item, j) => (
                    <div key={j} style={{
                      display: 'flex', justifyContent: 'space-between',
                      padding: '8px 0', borderTop: '1px solid rgba(255,255,255,0.04)',
                    }}>
                      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                        {item.image && (
                          <img src={item.image} alt={item.product_name}
                            style={{ width: 40, height: 40, objectFit: 'cover', opacity: 0.8 }} />
                        )}
                        <div>
                          <p style={{ fontSize: 13, color: '#fff' }}>{item.product_name}</p>
                          {item.size && (
                            <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>Taille : {item.size}</p>
                          )}
                        </div>
                      </div>
                      <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.5)' }}>×{item.quantity}</p>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </div>
  )
}
