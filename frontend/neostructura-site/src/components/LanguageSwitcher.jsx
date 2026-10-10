import { useState, useRef, useEffect } from 'react'
import { useLanguage, LANGUAGES } from '../i18n/LanguageContext'

export default function LanguageSwitcher({ compact = false }) {
  const { lang, setLang } = useLanguage()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const current = LANGUAGES.find(l => l.code === lang) || LANGUAGES[0]

  useEffect(() => {
    if (!open) return
    const onClickOutside = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [open])

  if (compact) {
    return (
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {LANGUAGES.map(l => (
          <button
            key={l.code} type="button" onClick={() => setLang(l.code)}
            aria-pressed={l.code === lang}
            style={{
              padding: '6px 12px', borderRadius: 6, fontSize: 12.5, fontWeight: 700,
              border: '1px solid ' + (l.code === lang ? 'var(--accent)' : 'var(--border)'),
              background: l.code === lang ? 'var(--bg-subtle)' : 'transparent',
              color: l.code === lang ? 'var(--accent)' : 'var(--text)',
            }}
          >
            {l.label}
          </button>
        ))}
      </div>
    )
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        type="button" onClick={() => setOpen(v => !v)} aria-label="Changer de langue" aria-expanded={open}
        style={{
          width: 38, height: 38, borderRadius: '50%',
          border: '1px solid var(--border)', background: 'var(--bg-elevated)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11.5, fontWeight: 700, color: 'var(--text)',
        }}
      >
        {current.label}
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: '110%', right: 0, zIndex: 10,
          background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 10,
          boxShadow: 'var(--shadow-lift)', padding: 6, display: 'flex', flexDirection: 'column', gap: 2, minWidth: 140,
        }}>
          {LANGUAGES.map(l => (
            <button
              key={l.code} type="button"
              onClick={() => { setLang(l.code); setOpen(false) }}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
                padding: '9px 12px', borderRadius: 6, fontSize: 13.5, fontWeight: 600, textAlign: 'left',
                background: l.code === lang ? 'var(--bg-subtle)' : 'transparent',
                color: l.code === lang ? 'var(--accent)' : 'var(--text)',
              }}
            >
              <span>{l.name}</span>
              <span style={{ fontSize: 11, opacity: 0.7 }}>{l.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
