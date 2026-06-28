import { useState } from 'react'
import { motion } from 'framer-motion'
import MakeupLayout from '../layouts/MakeupLayout'

export default function MakeupContact() {
  const [form,   setForm]   = useState({ name: '', email: '', subject: '', message: '' })
  const [status, setStatus] = useState('idle')

  const handleChange = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  const handleSubmit = async e => {
    e.preventDefault()
    setStatus('loading')
    await new Promise(r => setTimeout(r, 800))
    setStatus('success')
  }

  return (
    <MakeupLayout>
      {/* Banner */}
      <section style={{ background: 'var(--beauty-white)', borderBottom: '1px solid var(--beauty-border)', padding: '56px 0' }}>
        <div className="beauty-container" style={{ textAlign: 'center' }}>
          <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.2em', color: 'var(--beauty-gold)', marginBottom: 12, textTransform: 'uppercase' }}>
            SIÈCLE BEAUTY
          </p>
          <h1 style={{
            fontFamily: 'var(--beauty-serif)',
            fontSize: 'clamp(2rem, 5vw, 3.5rem)',
            fontWeight: 400,
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            color: 'var(--beauty-black)',
          }}>
            Contact
          </h1>
          <p style={{ color: 'var(--beauty-muted)', fontSize: 14, marginTop: 16, maxWidth: 480, margin: '16px auto 0' }}>
            Notre équipe beauté est disponible du lundi au vendredi, de 9h à 18h.
          </p>
        </div>
      </section>

      {/* Content */}
      <section style={{ padding: '80px 0' }}>
        <div className="beauty-container" style={{ display: 'grid', gridTemplateColumns: '1fr 1.4fr', gap: 80, alignItems: 'start' }}>
          {/* Info */}
          <motion.div
            initial={{ opacity: 0, x: -24 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.7 }}
          >
            <h2 style={{ fontFamily: 'var(--beauty-serif)', fontSize: '1.6rem', fontWeight: 400, letterSpacing: '0.08em', marginBottom: 32, color: 'var(--beauty-black)' }}>
              Nous contacter
            </h2>
            {[
              { label: 'E-mail', value: 'hello@siecle-beauty.com', href: 'mailto:hello@siecle-beauty.com' },
              { label: 'Téléphone', value: '+33 1 23 45 67 89', href: 'tel:+33123456789' },
              { label: 'Horaires', value: 'Lun – Ven : 9h – 18h', href: null },
            ].map(({ label, value, href }) => (
              <div key={label} style={{ marginBottom: 28 }}>
                <p style={{ fontSize: 9, fontWeight: 800, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--beauty-muted)', marginBottom: 6 }}>{label}</p>
                {href
                  ? <a href={href} style={{ fontSize: 15, color: 'var(--beauty-gold)', fontWeight: 500 }}>{value}</a>
                  : <p style={{ fontSize: 15, color: 'var(--beauty-brown)' }}>{value}</p>
                }
              </div>
            ))}
          </motion.div>

          {/* Form */}
          <motion.div
            initial={{ opacity: 0, x: 24 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
          >
            {status === 'success' ? (
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                style={{ textAlign: 'center', padding: '60px 0' }}
              >
                <p style={{ fontSize: 32, marginBottom: 16 }}>✓</p>
                <p style={{ fontFamily: 'var(--beauty-serif)', fontSize: '1.4rem', color: 'var(--beauty-black)', marginBottom: 12 }}>
                  Message envoyé
                </p>
                <p style={{ color: 'var(--beauty-muted)', fontSize: 14 }}>
                  Nous vous répondrons dans les meilleurs délais.
                </p>
              </motion.div>
            ) : (
              <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {[
                  { name: 'name',    label: 'Nom complet',    type: 'text',  required: true },
                  { name: 'email',   label: 'Adresse e-mail', type: 'email', required: true },
                  { name: 'subject', label: 'Sujet',          type: 'text',  required: true },
                ].map(f => (
                  <div key={f.name}>
                    <label style={{ display: 'block', fontSize: 9, fontWeight: 800, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--beauty-brown)', marginBottom: 8 }}>
                      {f.label}
                    </label>
                    <input
                      type={f.type}
                      name={f.name}
                      value={form[f.name]}
                      onChange={handleChange}
                      required={f.required}
                      style={{ width: '100%', height: 48, padding: '0 16px', background: 'var(--beauty-white)', border: '1.5px solid var(--beauty-border)', fontSize: 14, color: 'var(--beauty-black)', outline: 'none', fontFamily: 'var(--beauty-sans)' }}
                    />
                  </div>
                ))}
                <div>
                  <label style={{ display: 'block', fontSize: 9, fontWeight: 800, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--beauty-brown)', marginBottom: 8 }}>
                    Message
                  </label>
                  <textarea
                    name="message"
                    value={form.message}
                    onChange={handleChange}
                    required
                    rows={5}
                    style={{ width: '100%', padding: '14px 16px', background: 'var(--beauty-white)', border: '1.5px solid var(--beauty-border)', fontSize: 14, color: 'var(--beauty-black)', outline: 'none', resize: 'vertical', fontFamily: 'var(--beauty-sans)' }}
                  />
                </div>
                <button
                  type="submit"
                  className="beauty-btn"
                  disabled={status === 'loading'}
                  style={{ alignSelf: 'flex-start' }}
                >
                  {status === 'loading' ? 'Envoi…' : 'Envoyer le message'}
                </button>
              </form>
            )}
          </motion.div>
        </div>
      </section>

      <style>{`
        @media (max-width: 768px) {
          .beauty-container { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </MakeupLayout>
  )
}
