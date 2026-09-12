import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import fr from './dictionaries/fr'
import en from './dictionaries/en'
import de from './dictionaries/de'
import pt from './dictionaries/pt'

const DICTS = { fr, en, de, pt }
const STORAGE_KEY = 'neostructura_lang'

export const LANGUAGES = [
  { code: 'fr', label: 'FR', name: 'Français' },
  { code: 'en', label: 'EN', name: 'English' },
  { code: 'de', label: 'DE', name: 'Deutsch' },
  { code: 'pt', label: 'PT', name: 'Português' },
]

function detectDefaultLang() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored && DICTS[stored]) return stored
  } catch {
    // localStorage indisponible (navigation privée, etc.) — ignore et retombe sur la détection navigateur.
  }
  const nav = (navigator.language || 'fr').slice(0, 2).toLowerCase()
  return DICTS[nav] ? nav : 'fr'
}

const LanguageContext = createContext(null)

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(detectDefaultLang)

  useEffect(() => {
    document.documentElement.lang = lang
    try {
      window.localStorage.setItem(STORAGE_KEY, lang)
    } catch {
      // best-effort — la langue reste au moins active pour la session en cours.
    }
  }, [lang])

  const setLang = (code) => {
    if (DICTS[code]) setLangState(code)
  }

  const value = useMemo(() => ({ lang, setLang, dict: DICTS[lang] || DICTS.fr }), [lang])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

// Retombe silencieusement sur le français (plutôt que de lever une
// exception qui ferait planter toute la page) si un composant est monté
// hors du LanguageProvider — filet de sécurité, ne devrait pas arriver en
// usage normal puisque App.jsx enveloppe toute l'application.
export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) return { lang: 'fr', setLang: () => {}, dict: DICTS.fr }
  return ctx
}
