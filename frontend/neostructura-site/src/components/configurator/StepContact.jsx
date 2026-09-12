const labelStyle = { display: 'block', fontSize: 12.5, fontWeight: 600, marginBottom: 8, color: 'var(--text-muted)' }
const inputStyle = {
  width: '100%', padding: '12px 14px', borderRadius: 8, border: '1px solid var(--border)',
  background: 'var(--bg)', color: 'var(--text)', fontFamily: 'inherit', fontSize: 14, resize: 'vertical',
}

export default function StepContact({ contact, building, notes, onChangeContact, onChangeBuilding, onChangeNotes, onSubmit, onBack, submitting, error }) {
  const set = (field) => (e) => onChangeContact({ ...contact, [field]: e.target.value })
  const setBuilding = (field) => (e) => onChangeBuilding({ ...building, [field]: e.target.value })
  const valid = contact.first_name && contact.last_name && contact.email

  return (
    <div>
      <h2 style={{ fontSize: 24, marginBottom: 8 }}>Vos coordonnées.</h2>
      <p style={{ color: 'var(--text-muted)', fontSize: 14.5, marginBottom: 32 }}>
        Pour vous transmettre votre estimation et organiser l'intervention.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }} id="neo-cfg-contact-row1">
        <div>
          <label style={labelStyle}>Prénom *</label>
          <input type="text" value={contact.first_name || ''} onChange={set('first_name')} style={inputStyle} required />
        </div>
        <div>
          <label style={labelStyle}>Nom *</label>
          <input type="text" value={contact.last_name || ''} onChange={set('last_name')} style={inputStyle} required />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }} id="neo-cfg-contact-row2">
        <div>
          <label style={labelStyle}>Email *</label>
          <input type="email" value={contact.email || ''} onChange={set('email')} style={inputStyle} required />
        </div>
        <div>
          <label style={labelStyle}>Téléphone</label>
          <input type="tel" value={contact.phone || ''} onChange={set('phone')} style={inputStyle} />
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Adresse d'intervention</label>
        <input type="text" value={building.address || ''} onChange={setBuilding('address')} style={inputStyle} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }} id="neo-cfg-contact-row3">
        <div>
          <label style={labelStyle}>Code postal</label>
          <input type="text" value={building.zip_code || ''} onChange={setBuilding('zip_code')} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>Ville</label>
          <input type="text" value={building.city || ''} onChange={setBuilding('city')} style={inputStyle} />
        </div>
      </div>

      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>Message (optionnel)</label>
        <textarea rows={4} value={notes || ''} onChange={(e) => onChangeNotes(e.target.value)} style={inputStyle} />
      </div>

      {error && <div style={{ color: '#C0392B', fontSize: 13.5, marginBottom: 16 }}>{error}</div>}

      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
        <button type="button" className="neo-btn neo-btn-outline" onClick={onBack} disabled={submitting}>Retour</button>
        <button
          type="button" className="neo-btn neo-btn-primary neo-btn-lg"
          disabled={!valid || submitting} onClick={onSubmit}
          style={{ opacity: (!valid || submitting) ? 0.6 : 1 }}
        >
          {submitting ? 'Envoi en cours…' : 'Envoyer ma demande'}
        </button>
      </div>

      <style>{`
        @media (max-width: 640px) {
          #neo-cfg-contact-row1, #neo-cfg-contact-row2, #neo-cfg-contact-row3 { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  )
}
