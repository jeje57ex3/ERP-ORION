import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'

export default function SearchOverlayInput({ theme = 'dark' }) {
  const [open,  setOpen]  = useState(false)
  const [query, setQuery] = useState('')
  const inputRef          = useRef(null)
  const wrapRef           = useRef(null)
  const navigate          = useNavigate()

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus()
  }, [open])

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') { setOpen(false); setQuery('') }
      if (e.key === 'Enter' && open && query.trim()) {
        navigate(`/search?q=${encodeURIComponent(query.trim())}`)
        setOpen(false)
        setQuery('')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, query, navigate])

  useEffect(() => {
    function onClickOut(e) {
      if (open && wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false)
        setQuery('')
      }
    }
    document.addEventListener('mousedown', onClickOut)
    return () => document.removeEventListener('mousedown', onClickOut)
  }, [open])

  const isDark = theme === 'dark'

  return (
    <div ref={wrapRef} className={`search-expand search-expand-${theme}`}>
      <motion.div
        className="search-expand-box"
        initial={false}
        animate={{ width: open ? 280 : 38 }}
        transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      >
        <AnimatePresence>
          {open && (
            <motion.input
              ref={inputRef}
              key="si"
              className="search-expand-input"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Rechercher…"
              aria-label="Rechercher"
            />
          )}
        </AnimatePresence>

        <button
          type="button"
          className="search-expand-btn"
          onClick={() => setOpen(v => !v)}
          aria-label={open ? 'Fermer la recherche' : 'Ouvrir la recherche'}
        >
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="1.5">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </button>
      </motion.div>
    </div>
  )
}
