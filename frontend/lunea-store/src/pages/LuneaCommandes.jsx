import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

const STATUS_LABELS = {
  pending:    { label: 'En attente', color: '#C6A15B' },
  confirmed:  { label: 'Confirmée', color: '#0891B2' },
  shipped:    { label: 'Expédiée', color: '#7C3AED' },
  delivered:  { label: 'Livrée', color: '#16A34A' },
  cancelled:  { label: 'Annulée', color: '#DC2626' },
  refunded:   { label: 'Remboursée', color: '#6B7280' },
}

function OrderCard({ order }) {
  const status = STATUS_LABELS[order.status] || { label: order.status, color: '#6B7280' }
  return (
    <div style={{
      background: 'var(--color-surface)', border: '1px solid var(--color-border)',
      borderRadius: 'var(--radius)', padding: '1.25rem 1.5rem', marginBottom: 12,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
        <div>
          <p style={{ fontFamily: 'var(--font-heading)', fontSize: '0.95rem', marginBottom: 4 }}>
            Commande #{order.reference || order.id}
          </p>
          <p style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
            {order.created_at ? new Date(order.created_at).toLocaleDateString('fr-FR', { year: 'numeric', month: 'long', day: 'numeric' }) : ''}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{
            fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 20,
            background: `${status.color}20`, color: status.color,
          }}>{status.label}</span>
          <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1rem' }}>
            {Number(order.total || 0).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
          </p>
        </div>
      </div>
      {order.items && order.items.length > 0 && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--color-border)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {order.items.slice(0, 3).map((item, i) => (
            <div key={i} style={{
              fontSize: 12, color: 'var(--color-text-muted)',
              background: 'var(--color-bg)', borderRadius: 6, padding: '3px 8px',
            }}>
              {item.name} × {item.quantity}
            </div>
          ))}
          {order.items.length > 3 && (
            <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>+{order.items.length - 3} autres</span>
          )}
        </div>
      )}
    </div>
  )
}

export default function LuneaCommandes() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    document.title = 'Mes commandes — LUNEA'
    fetch('/api/v1/lunea/customer/orders/', { credentials: 'include' })
      .then(r => {
        if (r.status === 401) { navigate('/lunea/login/'); return null }
        return r.ok ? r.json() : null
      })
      .then(d => setOrders(d?.results ?? d ?? []))
      .catch(() => setOrders([]))
      .finally(() => setLoading(false))
  }, [navigate])

  return (
    <div style={{ paddingTop: 'var(--header-h)' }}>
      <section className="lunea-section">
        <div className="lunea-container" style={{ maxWidth: 760 }}>
          <Link to="/lunea/compte/" style={{ fontSize: 12, color: 'var(--color-text-muted)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4, marginBottom: '1.5rem' }}>
            ← Mon compte
          </Link>
          <p className="lunea-eyebrow">Compte</p>
          <h1 className="lunea-heading" style={{ marginBottom: '2rem' }}>Mes commandes</h1>

          {loading ? (
            <p style={{ color: 'var(--color-text-muted)', textAlign: 'center', padding: '3rem' }}>Chargement...</p>
          ) : orders.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '4rem' }}>
              <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', marginBottom: '0.75rem' }}>Aucune commande</p>
              <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: '2rem' }}>Vous n'avez pas encore passé de commande.</p>
              <Link to="/lunea/boutique/" className="btn-primary">Découvrir la boutique</Link>
            </div>
          ) : (
            <>
              <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: '1.5rem' }}>{orders.length} commande{orders.length > 1 ? 's' : ''}</p>
              {orders.map(o => <OrderCard key={o.id} order={o} />)}
            </>
          )}
        </div>
      </section>
    </div>
  )
}
