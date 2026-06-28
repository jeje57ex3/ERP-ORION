import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function MakeupNewsletter() {
  const [email,  setEmail]  = useState('')
  const [status, setStatus] = useState('idle') // idle | loading | success | error

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email.includes('@')) return
    setStatus('loading')
    try {
      const res = await fetch('/api/v1/siecle/newsletter/', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email, source: 'makeup_home', brand: 'SIÈCLE BEAUTY' }),
      })
      setStatus(res.ok ? 'success' : 'error')
    } catch {
      setStatus('error')
    }
  }

  return (
    <section className="makeup-newsletter">
      <div className="beauty-container">
        <div className="makeup-newsletter-inner">
          <motion.div
            initial={{ opacity: 0, x: -24 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.7 }}
            viewport={{ once: true }}
          >
            <h2 className="makeup-newsletter-title">
              Rejoignez l'univers SIÈCLE
            </h2>
            <p className="makeup-newsletter-desc">
              Inscrivez-vous à notre newsletter et profitez de&nbsp;
              <strong>−10&nbsp;%</strong> sur votre première commande.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 24 }}
            whileInView={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.7, delay: 0.1 }}
            viewport={{ once: true }}
          >
            <AnimatePresence mode="wait">
              {status === 'success' ? (
                <motion.p
                  key="success"
                  className="makeup-newsletter-success"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                >
                  Merci ! Votre code −10&nbsp;% vous a été envoyé par e-mail.
                </motion.p>
              ) : (
                <motion.form
                  key="form"
                  className="makeup-newsletter-form"
                  onSubmit={handleSubmit}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <input
                    type="email"
                    className="makeup-newsletter-input"
                    placeholder="Votre adresse e-mail"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    required
                  />
                  <button
                    type="submit"
                    className="makeup-newsletter-submit"
                    disabled={status === 'loading'}
                  >
                    {status === 'loading' ? '…' : "S'inscrire"}
                  </button>
                </motion.form>
              )}
            </AnimatePresence>
            {status === 'error' && (
              <p className="makeup-newsletter-error">
                Une erreur est survenue. Veuillez réessayer.
              </p>
            )}
          </motion.div>
        </div>
      </div>
    </section>
  )
}
