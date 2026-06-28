import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function CommunityUploadForm({ onSuccess, onClose }) {
  const [preview, setPreview] = useState(null)
  const [caption, setCaption] = useState('')
  const [universe, setUniverse] = useState('vetements')
  const [submitting, setSubmitting] = useState(false)
  const fileRef = useRef()

  const onFile = (e) => {
    const f = e.target.files[0]
    if (!f) return
    const url = URL.createObjectURL(f)
    setPreview({ url, file: f })
  }

  const submit = async () => {
    if (!preview) return
    setSubmitting(true)
    try {
      const fd = new FormData()
      fd.append('image', preview.file)
      fd.append('caption', caption)
      fd.append('universe', universe)
      const { createPost } = await import('../../api/community')
      const data = await createPost(fd)
      onSuccess?.(data)
    } catch {
      alert('Erreur lors de la publication.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
      style={{ background: '#0d0d0d', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 24, padding: 32, maxWidth: 480, width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h3 style={{ fontSize: 15, fontWeight: 800, color: '#fff', letterSpacing: '0.1em' }}>PARTAGER MON LOOK</h3>
        {onClose && <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#666', fontSize: 20, cursor: 'pointer' }}>✕</button>}
      </div>

      {/* Image picker */}
      <div onClick={() => fileRef.current?.click()}
        style={{ aspect: '1', aspectRatio: '1', background: '#111', borderRadius: 16, border: '1.5px dashed rgba(255,255,255,0.12)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', marginBottom: 20, minHeight: 200 }}>
        {preview ? (
          <img src={preview.url} alt="preview" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <div style={{ textAlign: 'center', color: '#444' }}>
            <div style={{ fontSize: 40, marginBottom: 10 }}>📷</div>
            <div style={{ fontSize: 13 }}>Cliquez pour choisir une photo</div>
          </div>
        )}
      </div>
      <input ref={fileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={onFile} />

      <textarea value={caption} onChange={e => setCaption(e.target.value)} placeholder="Décrivez votre look, les produits portés…" rows={3}
        style={{ width: '100%', background: '#111', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, padding: '14px 16px', color: '#fff', fontSize: 13, fontFamily: 'inherit', resize: 'none', outline: 'none', marginBottom: 16 }} />

      <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
        {['vetements', 'montres', 'maquillage'].map(u => (
          <button key={u} onClick={() => setUniverse(u)}
            style={{ flex: 1, padding: '10px 8px', background: universe === u ? '#fff' : '#111', color: universe === u ? '#000' : '#666', border: `1px solid ${universe === u ? '#fff' : 'rgba(255,255,255,0.08)'}`, borderRadius: 8, fontSize: 11, fontWeight: 700, cursor: 'pointer', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            {u}
          </button>
        ))}
      </div>

      <button onClick={submit} disabled={!preview || submitting}
        style={{ width: '100%', padding: '15px', background: preview ? '#fff' : '#1a1a1a', color: preview ? '#000' : '#444', border: 'none', borderRadius: 12, fontSize: 12, fontWeight: 800, letterSpacing: '0.14em', cursor: preview ? 'pointer' : 'not-allowed' }}>
        {submitting ? 'PUBLICATION…' : 'PUBLIER MON LOOK'}
      </button>
    </motion.div>
  )
}
