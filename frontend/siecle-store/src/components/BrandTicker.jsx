export default function BrandTicker({ items = ['SIÈCLE', 'VESTIAIRE URBAIN', 'TAILLEUR ITALIEN', 'CHAPITRE 001'] }) {
  const track = [...items, ...items, ...items, ...items]

  return (
    <div style={{
      background: 'var(--siecle-black)',
      borderTop: '1px solid var(--siecle-border)',
      borderBottom: '1px solid var(--siecle-border)',
      overflow: 'hidden', padding: '18px 0',
    }}>
      <div className="siecle-ticker-track" style={{
        display: 'flex', width: 'max-content',
        animation: 'siecle-ticker 26s linear infinite',
      }}>
        {track.map((item, i) => (
          <span key={i} style={{
            display: 'inline-flex', alignItems: 'center',
            color: 'var(--siecle-muted)', fontSize: 12, fontWeight: 600,
            letterSpacing: '0.2em', whiteSpace: 'nowrap', padding: '0 24px',
          }}>
            {item}
            <span style={{ color: 'var(--siecle-beige)', marginLeft: 24 }}>✦</span>
          </span>
        ))}
      </div>

      <style>{`
        @keyframes siecle-ticker {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        @media (prefers-reduced-motion: reduce) {
          .siecle-ticker-track { animation: none !important; }
        }
      `}</style>
    </div>
  )
}
