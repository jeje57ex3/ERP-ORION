import { useMemo } from 'react'
import {
  CASE_FINISH_COLORS,
  DIAL_COLORS,
  HANDS_COLORS,
  CROWN_COLORS,
  STRAP_COLORS,
  CASE_SIZE_SCALE,
} from '../../../utils/siecleWatchAtelier'

const CX = 150
const CY = 210
const BASE_R = 108

// ── Helpers ──────────────────────────────────────────────────────────────────

function toRad(deg) { return (deg * Math.PI) / 180 }

function polarToXY(angle, r, cx = CX, cy = CY) {
  const rad = toRad(angle - 90) // 0° at top
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

// ── Bezel ticks (fluted) ─────────────────────────────────────────────────────
function FlutedBezel({ r, color }) {
  const ticks = []
  for (let i = 0; i < 60; i++) {
    const angle = i * 6
    const outer = polarToXY(angle, r)
    const inner = polarToXY(angle, r - 9)
    ticks.push(
      <line key={i}
        x1={outer.x} y1={outer.y}
        x2={inner.x} y2={inner.y}
        stroke={color} strokeWidth="2.2" strokeLinecap="round" opacity={0.7}
      />
    )
  }
  return <g>{ticks}</g>
}

// ── Diamond bezel ─────────────────────────────────────────────────────────────
function DiamondBezel({ r }) {
  const gems = []
  for (let i = 0; i < 36; i++) {
    const angle = i * 10
    const { x, y } = polarToXY(angle, r - 5)
    gems.push(
      <rect key={i}
        x={x - 2.5} y={y - 2.5} width="5" height="5" rx="1"
        fill="#fff" opacity={0.85}
        transform={`rotate(${angle}, ${x}, ${y})`}
      />
    )
  }
  return <g>{gems}</g>
}

// ── Indexes ──────────────────────────────────────────────────────────────────
function WatchIndexes({ type, r, color, dialColor }) {
  const isLight = dialColor && ['ivory', 'champagne'].includes(dialColor)
  const indexColor = isLight ? '#1a1a1a' : color
  const items = []

  if (type === 'roman') {
    const labels = { 12: 'XII', 3: 'III', 6: 'VI', 9: 'IX' }
    for (let h = 1; h <= 12; h++) {
      const angle = h * 30
      const { x, y } = polarToXY(angle, r - 18)
      if (labels[h]) {
        items.push(
          <text key={h} x={x} y={y} textAnchor="middle" dominantBaseline="central"
            fill={indexColor} fontSize="10" fontFamily="Georgia, serif" fontWeight="400" opacity={0.9}
          >
            {labels[h]}
          </text>
        )
      } else {
        const { x: x2, y: y2 } = polarToXY(angle, r - 16)
        items.push(
          <circle key={h} cx={x2} cy={y2} r="2.5" fill={indexColor} opacity={0.65} />
        )
      }
    }
  } else if (type === 'minimal') {
    const big = [12, 3, 6, 9]
    for (let h = 1; h <= 12; h++) {
      const angle = h * 30
      const isBig = big.includes(h)
      const { x, y } = polarToXY(angle, r - (isBig ? 14 : 16))
      items.push(
        <circle key={h} cx={x} cy={y} r={isBig ? 4 : 2.5}
          fill={indexColor} opacity={isBig ? 0.9 : 0.5}
        />
      )
    }
  } else {
    // baton (default)
    for (let h = 1; h <= 12; h++) {
      const angle = h * 30
      const isMajor = [12, 3, 6, 9].includes(h)
      const len = isMajor ? 14 : 9
      const width = isMajor ? 3.5 : 2
      const outer = polarToXY(angle, r - 13)
      const inner = polarToXY(angle, r - 13 - len)
      items.push(
        <line key={h}
          x1={outer.x} y1={outer.y}
          x2={inner.x} y2={inner.y}
          stroke={indexColor} strokeWidth={width} strokeLinecap="round"
          opacity={isMajor ? 0.9 : 0.7}
        />
      )
    }
  }
  return <g>{items}</g>
}

// ── Hands ────────────────────────────────────────────────────────────────────
function WatchHands({ color }) {
  // 10:10 display
  const hourAngle = 305   // 10h00 + 10min offset
  const minuteAngle = 60  // 10 min
  const c = color || '#E0E0E0'

  return (
    <g>
      {/* Hour hand */}
      <g transform={`rotate(${hourAngle}, ${CX}, ${CY})`}>
        <rect x={CX - 4.5} y={CY - 58} width="9" height="62" rx="3" fill={c} />
        <rect x={CX - 3} y={CY - 60} width="6" height="8" rx="2" fill={c} opacity={0.6} />
      </g>
      {/* Minute hand */}
      <g transform={`rotate(${minuteAngle}, ${CX}, ${CY})`}>
        <rect x={CX - 3} y={CY - 78} width="6" height="84" rx="2.5" fill={c} />
        <rect x={CX - 2} y={CY - 80} width="4" height="8" rx="1.5" fill={c} opacity={0.5} />
      </g>
      {/* Seconds hand */}
      <g transform={`rotate(${minuteAngle + 34}, ${CX}, ${CY})`}>
        <rect x={CX - 1} y={CY - 82} width="2" height="92" rx="1" fill="#C0392B" opacity={0.9} />
      </g>
      {/* Center jewel */}
      <circle cx={CX} cy={CY} r="6" fill={c} />
      <circle cx={CX} cy={CY} r="3" fill="#050505" />
    </g>
  )
}

// ── Strap ────────────────────────────────────────────────────────────────────
function WatchStrap({ strapKey, scale }) {
  const strap = STRAP_COLORS[strapKey] || STRAP_COLORS.jubilee_steel
  const W = 60 * scale
  const LX = CX - W / 2
  const RX = CX + W / 2
  const topY = CY - BASE_R * scale - 5
  const botY = CY + BASE_R * scale + 5

  if (strap.type === 'metal' || strap.type === 'mesh') {
    const rows = []
    const linkH = 9
    const rowCount = 7
    for (let i = 0; i < rowCount; i++) {
      const y = topY - linkH - i * linkH
      rows.push(
        <g key={`top-${i}`}>
          <rect x={LX} y={y} width={W} height={linkH - 1} rx="2" fill={strap.fill} />
          <rect x={LX} y={y} width={W} height={2} rx="1" fill={strap.accent} opacity={0.5} />
          <line x1={LX + W * 0.33} y1={y} x2={LX + W * 0.33} y2={y + linkH - 1} stroke={strap.accent} strokeWidth="1" opacity={0.4} />
          <line x1={LX + W * 0.66} y1={y} x2={LX + W * 0.66} y2={y + linkH - 1} stroke={strap.accent} strokeWidth="1" opacity={0.4} />
        </g>
      )
    }
    for (let i = 0; i < rowCount; i++) {
      const y = botY + i * linkH
      rows.push(
        <g key={`bot-${i}`}>
          <rect x={LX} y={y} width={W} height={linkH - 1} rx="2" fill={strap.fill} />
          <rect x={LX} y={y + linkH - 3} width={W} height={2} rx="1" fill={strap.accent} opacity={0.4} />
          <line x1={LX + W * 0.33} y1={y} x2={LX + W * 0.33} y2={y + linkH - 1} stroke={strap.accent} strokeWidth="1" opacity={0.4} />
          <line x1={LX + W * 0.66} y1={y} x2={LX + W * 0.66} y2={y + linkH - 1} stroke={strap.accent} strokeWidth="1" opacity={0.4} />
        </g>
      )
    }
    return <g>{rows}</g>
  }

  // Leather / silicone / rubber
  const topStart = topY - 80
  const botEnd = botY + 90
  return (
    <g>
      {/* Top strap */}
      <path
        d={`M${LX + 10},${topStart} L${RX - 10},${topStart} L${RX + 2},${topY} L${LX - 2},${topY} Z`}
        fill={strap.fill}
      />
      <line x1={CX} y1={topStart} x2={CX} y2={topY} stroke={strap.accent} strokeWidth="1" opacity={0.3} />
      {/* Bottom strap */}
      <path
        d={`M${LX - 2},${botY} L${RX + 2},${botY} L${RX - 8},${botEnd} L${LX + 8},${botEnd} Z`}
        fill={strap.fill}
      />
      <line x1={CX} y1={botY} x2={CX} y2={botEnd} stroke={strap.accent} strokeWidth="1" opacity={0.3} />
      {/* Buckle hint */}
      <rect x={CX - 12} y={botEnd - 15} width="24" height="10" rx="3" fill={strap.accent} />
    </g>
  )
}

// ── Front face SVG ────────────────────────────────────────────────────────────
function FrontView({ configuration }) {
  const scale = CASE_SIZE_SCALE[configuration.caseSize] || 1
  const r = BASE_R * scale
  const innerR = r - 10
  const dialR = innerR - 5
  const caseC = CASE_FINISH_COLORS[configuration.caseFinish] || CASE_FINISH_COLORS.polished_steel
  const dialFill = DIAL_COLORS[configuration.dial] || DIAL_COLORS.black
  const handsColor = HANDS_COLORS[configuration.hands] || HANDS_COLORS.silver
  const crownColor = CROWN_COLORS[configuration.crown] || CROWN_COLORS.silver
  const isLightDial = ['ivory', 'champagne'].includes(configuration.dial)
  const dateTextColor = isLightDial ? '#333' : '#ddd'

  return (
    <>
      <WatchStrap strapKey={configuration.strap} scale={scale} />

      {/* Case shadow */}
      <circle cx={CX + 3} cy={CY + 5} r={r + 2} fill="rgba(0,0,0,0.45)" />

      {/* Case body */}
      <defs>
        <radialGradient id="caseGrad" cx="38%" cy="30%">
          <stop offset="0%" stopColor={caseC.highlight} />
          <stop offset="60%" stopColor={caseC.base} />
          <stop offset="100%" stopColor={caseC.shadow} />
        </radialGradient>
        <radialGradient id="dialGrad" cx="50%" cy="35%">
          <stop offset="0%" stopColor={dialFill} stopOpacity="0.7" />
          <stop offset="100%" stopColor={dialFill} />
        </radialGradient>
        <radialGradient id="crystalGrad" cx="45%" cy="25%">
          <stop offset="0%" stopColor="rgba(255,255,255,0.12)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </radialGradient>
      </defs>

      <circle cx={CX} cy={CY} r={r + 2} fill="url(#caseGrad)" />
      <circle cx={CX} cy={CY} r={r + 2} fill="none" stroke={caseC.stroke} strokeWidth="1.5" />

      {/* Bezel */}
      {configuration.bezel === 'fluted' && (
        <FlutedBezel r={r} color={caseC.highlight} />
      )}
      {configuration.bezel === 'diamond' && (
        <DiamondBezel r={r} />
      )}
      {configuration.bezel === 'red_signature' && (
        <circle cx={CX} cy={CY} r={r - 1} fill="none" stroke="#B02035" strokeWidth="7" opacity={0.8} />
      )}

      {/* Inner bezel ring */}
      <circle cx={CX} cy={CY} r={innerR} fill={caseC.shadow} opacity={0.6} />
      <circle cx={CX} cy={CY} r={innerR - 1} fill={caseC.base} opacity={0.4} />

      {/* Dial */}
      <circle cx={CX} cy={CY} r={dialR} fill={dialFill} />
      <circle cx={CX} cy={CY} r={dialR} fill="url(#dialGrad)" />

      {/* Sunburst texture on light dials */}
      {isLightDial && (
        <circle cx={CX} cy={CY} r={dialR} fill="none" stroke={isLightDial ? '#8B7A50' : '#fff'} strokeWidth="0.3" opacity={0.2} />
      )}

      {/* Brand name on dial */}
      <text x={CX} y={CY - 32} textAnchor="middle" fontSize="8.5"
        fontFamily="'Cormorant Garamond', Georgia, serif" fontWeight="400"
        fill={isLightDial ? '#3A3020' : '#D8C7A3'} letterSpacing="3" opacity={0.9}
      >
        SIÈCLE
      </text>
      <text x={CX} y={CY - 21} textAnchor="middle" fontSize="5.5"
        fontFamily="'Inter', sans-serif" fontWeight="600"
        fill={isLightDial ? '#5A5040' : '#8A7868'} letterSpacing="2" opacity={0.7}
      >
        SWISS MADE
      </text>

      {/* Date window at 3 o'clock */}
      <rect x={CX + 52} y={CY - 7} width="20" height="14" rx="2"
        fill={isLightDial ? '#e8e0d0' : '#2A2A2A'} stroke={dateTextColor} strokeWidth="0.5" opacity={0.85}
      />
      <text x={CX + 62} y={CY + 2} textAnchor="middle" dominantBaseline="central"
        fontSize="7" fontFamily="'Inter', sans-serif" fontWeight="700"
        fill={isLightDial ? '#2A2010' : '#E8E0D0'} opacity={0.9}
      >
        19
      </text>

      {/* Indexes */}
      <WatchIndexes type={configuration.indexes} r={dialR} color={isLightDial ? '#4A3828' : '#D0C8B0'} dialColor={configuration.dial} />

      {/* Hands */}
      <WatchHands color={handsColor} />

      {/* Crystal reflection */}
      <ellipse cx={CX - 28} cy={CY - 38} rx={32} ry={18}
        fill="url(#crystalGrad)" transform={`rotate(-30, ${CX - 28}, ${CY - 38})`}
      />

      {/* Crown */}
      <rect x={CX + r + 1} y={CY - 7} width="16" height="14" rx="4"
        fill={crownColor} stroke={caseC.shadow} strokeWidth="1"
      />
      <line x1={CX + r + 4} y1={CY - 4} x2={CX + r + 13} y2={CY - 4} stroke={caseC.shadow} strokeWidth="1" opacity={0.4} />
      <line x1={CX + r + 4} y1={CY} x2={CX + r + 13} y2={CY} stroke={caseC.shadow} strokeWidth="1" opacity={0.4} />
      <line x1={CX + r + 4} y1={CY + 4} x2={CX + r + 13} y2={CY + 4} stroke={caseC.shadow} strokeWidth="1" opacity={0.4} />
    </>
  )
}

// ── Side / profile view ───────────────────────────────────────────────────────
function SideView({ configuration }) {
  const caseC = CASE_FINISH_COLORS[configuration.caseFinish] || CASE_FINISH_COLORS.polished_steel
  const crownColor = CROWN_COLORS[configuration.crown] || CROWN_COLORS.silver
  const strap = STRAP_COLORS[configuration.strap] || STRAP_COLORS.jubilee_steel
  const thickness = 30

  return (
    <>
      <defs>
        <linearGradient id="sideGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={caseC.shadow} />
          <stop offset="30%" stopColor={caseC.highlight} />
          <stop offset="70%" stopColor={caseC.base} />
          <stop offset="100%" stopColor={caseC.shadow} />
        </linearGradient>
      </defs>
      {/* Top strap (side) */}
      <rect x={CX - 28} y={30} width={56} height={CY - BASE_R - 30} rx="4" fill={strap.fill} />
      {/* Case side */}
      <rect x={CX - thickness / 2} y={CY - BASE_R} width={thickness} height={BASE_R * 2}
        rx="8" fill="url(#sideGrad)"
      />
      <rect x={CX - thickness / 2} y={CY - BASE_R} width={thickness} height={BASE_R * 2}
        rx="8" fill="none" stroke={caseC.stroke} strokeWidth="1.5"
      />
      {/* Crystal edge */}
      <rect x={CX - thickness / 2 + 4} y={CY - BASE_R + 4} width={thickness - 8} height={BASE_R * 2 - 8}
        rx="5" fill="rgba(180,220,255,0.08)"
      />
      {/* Crown */}
      <ellipse cx={CX + thickness / 2 + 8} cy={CY} rx="10" ry="7"
        fill={crownColor} stroke={caseC.shadow} strokeWidth="1"
      />
      {/* Bottom strap */}
      <rect x={CX - 28} y={CY + BASE_R} width={56} height={CY - BASE_R - 30} rx="4" fill={strap.fill} />
    </>
  )
}

// ── Back view ─────────────────────────────────────────────────────────────────
function BackView({ configuration }) {
  const scale = CASE_SIZE_SCALE[configuration.caseSize] || 1
  const r = BASE_R * scale
  const caseC = CASE_FINISH_COLORS[configuration.caseFinish] || CASE_FINISH_COLORS.polished_steel
  const engravingText = configuration.engraving?.enabled ? configuration.engraving.text : ''

  return (
    <>
      <WatchStrap strapKey={configuration.strap} scale={scale} />
      <circle cx={CX + 3} cy={CY + 4} r={r + 2} fill="rgba(0,0,0,0.4)" />
      <defs>
        <radialGradient id="backGrad" cx="60%" cy="40%">
          <stop offset="0%" stopColor={caseC.highlight} />
          <stop offset="60%" stopColor={caseC.base} />
          <stop offset="100%" stopColor={caseC.shadow} />
        </radialGradient>
      </defs>
      <circle cx={CX} cy={CY} r={r + 2} fill="url(#backGrad)" />
      <circle cx={CX} cy={CY} r={r + 2} fill="none" stroke={caseC.stroke} strokeWidth="1.5" />
      {/* Caseback engravable area */}
      <circle cx={CX} cy={CY} r={r - 18} fill="none" stroke={caseC.shadow} strokeWidth="1" opacity={0.5} strokeDasharray="4 3" />
      <circle cx={CX} cy={CY} r={r - 20} fill={caseC.shadow} opacity={0.3} />
      {/* SIÈCLE on back */}
      <text x={CX} y={CY - 30} textAnchor="middle" fontSize="9"
        fontFamily="'Cormorant Garamond', Georgia, serif"
        fill={caseC.highlight} letterSpacing="4" opacity={0.85}
      >
        SIÈCLE
      </text>
      {/* Screw holes */}
      {[0, 90, 180, 270].map(angle => {
        const { x, y } = polarToXY(angle, r - 8)
        return <circle key={angle} cx={x} cy={y} r="4" fill={caseC.shadow} stroke={caseC.highlight} strokeWidth="1" opacity={0.8} />
      })}
      {/* Engraving */}
      {engravingText ? (
        <>
          <text x={CX} y={CY + 8} textAnchor="middle" fontSize="11"
            fontFamily="'Cormorant Garamond', Georgia, serif" fontStyle="italic"
            fill={caseC.highlight} opacity={0.9}
          >
            {engravingText.slice(0, 14)}
          </text>
          {engravingText.length > 14 && (
            <text x={CX} y={CY + 22} textAnchor="middle" fontSize="11"
              fontFamily="'Cormorant Garamond', Georgia, serif" fontStyle="italic"
              fill={caseC.highlight} opacity={0.9}
            >
              {engravingText.slice(14)}
            </text>
          )}
        </>
      ) : (
        <text x={CX} y={CY + 12} textAnchor="middle" fontSize="8"
          fontFamily="'Inter', sans-serif" fill={caseC.base} opacity={0.4} letterSpacing="2"
        >
          GRAVURE PERSONNELLE
        </text>
      )}
      <text x={CX} y={CY + 44} textAnchor="middle" fontSize="7"
        fontFamily="'Inter', sans-serif" fill={caseC.base} opacity={0.4} letterSpacing="1"
      >
        NO. A{Math.floor(Math.random() * 9000 + 1000)}/9999
      </text>
    </>
  )
}

// ── Wrist view (perspective) ──────────────────────────────────────────────────
function WristView({ configuration }) {
  const scale = CASE_SIZE_SCALE[configuration.caseSize] || 1
  const r = BASE_R * scale
  const caseC = CASE_FINISH_COLORS[configuration.caseFinish] || CASE_FINISH_COLORS.polished_steel
  const dialFill = DIAL_COLORS[configuration.dial] || DIAL_COLORS.black
  const handsColor = HANDS_COLORS[configuration.hands] || HANDS_COLORS.silver
  const strap = STRAP_COLORS[configuration.strap] || STRAP_COLORS.jubilee_steel

  return (
    <>
      <defs>
        <radialGradient id="wristGrad" cx="50%" cy="35%">
          <stop offset="0%" stopColor={caseC.highlight} />
          <stop offset="65%" stopColor={caseC.base} />
          <stop offset="100%" stopColor={caseC.shadow} />
        </radialGradient>
        <radialGradient id="wristDialGrad" cx="45%" cy="30%">
          <stop offset="0%" stopColor={dialFill} stopOpacity={0.75} />
          <stop offset="100%" stopColor={dialFill} />
        </radialGradient>
        {/* Perspective ellipse clip */}
        <clipPath id="wristClip">
          <ellipse cx={CX} cy={CY} rx={r + 3} ry={(r + 3) * 0.72} />
        </clipPath>
      </defs>

      {/* Wrist silhouette */}
      <ellipse cx={CX} cy={CY + r + 28} rx={80} ry={30} fill="#2A2220" opacity={0.6} />
      <rect x={CX - 78} y={CY + r - 4} width={156} height={80} rx="40" fill="#2A2220" opacity={0.6} />

      {/* Strap on wrist */}
      <rect x={CX - 40} y={CY - r - 10} width={80} height={r * 2 + 20 + 80} rx="8" fill={strap.fill} opacity={0.9} />

      {/* Case (ellipse/perspective) */}
      <ellipse cx={CX + 2} cy={CY + 4} rx={r + 3} ry={(r + 3) * 0.72} fill="rgba(0,0,0,0.4)" />
      <ellipse cx={CX} cy={CY} rx={r + 2} ry={(r + 2) * 0.72} fill="url(#wristGrad)" />

      {/* Dial */}
      <ellipse cx={CX} cy={CY} rx={r - 15} ry={(r - 15) * 0.72} fill={dialFill} />
      <ellipse cx={CX} cy={CY} rx={r - 15} ry={(r - 15) * 0.72} fill="url(#wristDialGrad)" />

      {/* Brand name */}
      <text x={CX} y={CY - 16} textAnchor="middle" fontSize="8"
        fontFamily="'Cormorant Garamond', Georgia, serif"
        fill={['ivory', 'champagne'].includes(configuration.dial) ? '#3A3020' : '#D8C7A3'}
        letterSpacing="3" opacity={0.85} transform={`scale(1, 0.72) translate(0, ${CY * 0.28})`}
      >
        SIÈCLE
      </text>

      {/* Hands (simplified on ellipse) */}
      <g clipPath="url(#wristClip)">
        <g transform={`rotate(305, ${CX}, ${CY})`}>
          <rect x={CX - 3.5} y={CY - 46} width="7" height="50" rx="2.5"
            fill={handsColor} transform={`scale(1, 0.72) translate(0, ${CY * 0.28})`}
          />
        </g>
        <g transform={`rotate(60, ${CX}, ${CY})`}>
          <rect x={CX - 2} y={CY - 62} width="4" height="68" rx="2"
            fill={handsColor} transform={`scale(1, 0.72) translate(0, ${CY * 0.28})`}
          />
        </g>
      </g>
      <ellipse cx={CX} cy={CY} rx="5" ry="3.6" fill={handsColor} />
    </>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function AtelierWatchSvgPreview({ configuration, viewMode }) {
  return (
    <svg
      viewBox="0 0 300 420"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Aperçu montre SIÈCLE"
      style={{ width: '100%', height: 'auto', filter: 'drop-shadow(0 20px 60px rgba(0,0,0,0.7))' }}
    >
      {viewMode === 'front' && <FrontView configuration={configuration} />}
      {viewMode === 'side'  && <SideView  configuration={configuration} />}
      {viewMode === 'wrist' && <WristView configuration={configuration} />}
      {viewMode === 'back'  && <BackView  configuration={configuration} />}
    </svg>
  )
}
