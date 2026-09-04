import { useState } from 'react'
import { Helmet } from 'react-helmet-async'
import Reveal from '../components/Reveal'
import { sendContactMessage } from '../api/contact'

const INITIAL = { name: '', email: '', phone: '', subject: '', message: '', website_url_field: '' }

export default function ContactPage() {
  const [form, setForm] = useState(INITIAL)
  const [status, setStatus] = useState('idle') // idle | sending | success | error
  const [error, setError] = useState('')

  const onChange = (e) => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  const onSubmit = async (e) => {
    e.preventDefault()
    setStatus('sending')
    setError('')
    try {
      await sendContactMessage(form)
      setStatus('success')
      setForm(INITIAL)
    } catch (err) {
      setStatus('error')
      setError(err.message)
    }
  }

  return (
    <>
      <Helmet><title>Contact — NÉOSTRUCTURA</title></Helmet>

      <section style={{ paddingTop: 'calc(var(--header-h) + 64px)', paddingBottom: 32 }}>
        <div className="neo-container">
          <Reveal style={{ maxWidth: 640 }}>
            <div className="neo-eyebrow">Contact</div>
            <h1 style={{ fontSize: 'clamp(30px, 4.6vw, 48px)', marginBottom: 18 }}>
              Parlons de votre projet.
            </h1>
            <p style={{ fontSize: 16, color: 'var(--text-muted)', lineHeight: 1.7 }}>
              Décrivez votre besoin, nous revenons vers vous rapidement avec une première estimation.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="neo-section" style={{ paddingTop: 8 }}>
        <div className="neo-container" style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: 48 }} id="neo-contact-layout">
          <Reveal>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
              {[
                { label: 'Email', value: 'contact@neostructura.fr', href: 'mailto:contact@neostructura.fr' },
                { label: 'Téléphone', value: '01 00 00 00 00', href: 'tel:+33100000000' },
                { label: 'Zone d\'intervention', value: 'Toute la région' },
              ].map(item => (
                <div key={item.label} className="neo-card" style={{ padding: 24 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--accent)', marginBottom: 8 }}>
                    {item.label}
                  </div>
                  {item.href
                    ? <a href={item.href} style={{ fontSize: 16, fontWeight: 600 }}>{item.value}</a>
                    : <span style={{ fontSize: 16, fontWeight: 600 }}>{item.value}</span>}
                </div>
              ))}
            </div>
          </Reveal>

          <Reveal delay={0.1} className="neo-card" style={{ padding: 40 }}>
            {status === 'success' ? (
              <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <div style={{ fontSize: 40, marginBottom: 16 }}>✓</div>
                <h3 style={{ fontSize: 20, marginBottom: 10 }}>Message envoyé</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: 14.5 }}>
                  Merci, nous revenons vers vous très rapidement.
                </p>
                <button className="neo-btn neo-btn-outline" style={{ marginTop: 24 }} onClick={() => setStatus('idle')}>
                  Envoyer un autre message
                </button>
              </div>
            ) : (
              <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                {/* Honeypot anti-spam, invisible pour un humain */}
                <input
                  type="text" name="website_url_field" value={form.website_url_field} onChange={onChange}
                  autoComplete="off" tabIndex={-1}
                  style={{ position: 'absolute', left: '-9999px', width: 1, height: 1, opacity: 0 }}
                  aria-hidden="true"
                />

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }} id="neo-form-row">
                  <Field label="Nom complet" name="name" value={form.name} onChange={onChange} required />
                  <Field label="Email" name="email" type="email" value={form.email} onChange={onChange} required />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }} id="neo-form-row2">
                  <Field label="Téléphone" name="phone" value={form.phone} onChange={onChange} />
                  <Field label="Sujet" name="subject" value={form.subject} onChange={onChange} />
                </div>
                <div>
                  <label style={labelStyle}>Message</label>
                  <textarea
                    name="message" value={form.message} onChange={onChange} required rows={6}
                    style={inputStyle}
                  />
                </div>

                {status === 'error' && (
                  <div style={{ color: '#C0392B', fontSize: 13.5 }}>{error}</div>
                )}

                <button type="submit" className="neo-btn neo-btn-primary neo-btn-lg" disabled={status === 'sending'}>
                  {status === 'sending' ? 'Envoi en cours…' : 'Envoyer ma demande'}
                </button>
              </form>
            )}
          </Reveal>
        </div>
      </section>

      <style>{`
        @media (max-width: 860px) {
          #neo-contact-layout { grid-template-columns: 1fr !important; }
          #neo-form-row, #neo-form-row2 { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </>
  )
}

const labelStyle = { display: 'block', fontSize: 12.5, fontWeight: 600, marginBottom: 8, color: 'var(--text-muted)' }
const inputStyle = {
  width: '100%', padding: '12px 14px', borderRadius: 8, border: '1px solid var(--border)',
  background: 'var(--bg)', color: 'var(--text)', fontFamily: 'inherit', fontSize: 14, resize: 'vertical',
}

function Field({ label, name, value, onChange, type = 'text', required = false }) {
  return (
    <div>
      <label style={labelStyle}>{label}{required && ' *'}</label>
      <input type={type} name={name} value={value} onChange={onChange} required={required} style={inputStyle} />
    </div>
  )
}
