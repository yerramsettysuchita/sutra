/**
 * The schema gap, drawn.
 *
 * This picture is the project. Three FIRs, three renderings of one man, no key
 * joining them. Then one resolved identity holding all three.
 *
 * It replaced three paragraphs of prose on the corpus audit screen. Prose
 * describing a data model is the slowest way to explain a data model.
 *
 * Colours are token literals rather than var() because SVG presentation
 * attributes do not inherit custom properties reliably across renderers, and
 * this figure has to survive being printed. They are the same values as
 * tokens.css and the contrast gate covers the pairs used here.
 */

const INK = '#14171C'
const INK2 = '#464D55'
const INK3 = '#656C75'
const LINE = '#CFCBC1'
const SUNKEN = '#F4F2EE'
const SURFACE = '#FFFFFF'
const RESOLVED_MID = '#2E9E6B'
const RESOLVED_DEEP = '#0F5D3C'
const RESOLVED_TINT = '#E4F3EA'
const CONFLICT_DEEP = '#8C2018'
const NAVY = '#16305C'

type Fir = { crime: string; name: string; kannada?: boolean; y: number }

const FIRS: Fir[] = [
  { crime: '1000420240000131', name: 'Suresh', y: 44 },
  { crime: '1001120250000078', name: 'Suresha', y: 130 },
  { crime: '1002220250000205', name: 'ಸುರೇಶ', kannada: true, y: 216 },
]

export function SchemaGap() {
  return (
    <svg
      className="gapfig"
      viewBox="0 0 700 300"
      role="img"
      aria-labelledby="gapfig-title gapfig-desc"
      preserveAspectRatio="xMidYMid meet"
    >
      <title id="gapfig-title">
        The missing person entity in the KSP schema
      </title>
      <desc id="gapfig-desc">
        On the left, three separate FIRs each carry an accused row for the same
        man, written as Suresh, Suresha and the Kannada rendering. Each row has
        its own AccusedMasterID and a PersonID of A1, which is a label within
        that FIR only. No column joins them, so the schema holds three
        unconnected people. On the right, SUTRA has resolved them into one
        identity, R000412, linked back to all three cases.
      </desc>

      {/* ---------------------------------------------------- left, as held */}
      <text x="16" y="20" fontSize="11" fontWeight="600" fill={INK3}
            letterSpacing="1.2">
        AS THE SCHEMA HOLDS IT
      </text>

      {FIRS.map((fir) => (
        <g key={fir.crime}>
          <rect
            x="16" y={fir.y} width="250" height="62" rx="3"
            fill={SURFACE} stroke={LINE} strokeWidth="1"
          />
          <text x="30" y={fir.y + 20} fontSize="10" fill={INK3}
                className="gapfig__mono">
            {fir.crime}
          </text>
          <text
            x="30" y={fir.y + 40}
            fontSize="15" fontWeight="500" fill={INK}
            className={fir.kannada ? 'gapfig__kn' : 'gapfig__mono'}
          >
            {fir.name}
          </text>
          <text x="30" y={fir.y + 54} fontSize="9.5" fill={INK3}
                className="gapfig__mono">
            PersonID A1
          </text>
          {/* Each row is its own island. The stub goes nowhere. */}
          <line
            x1="266" y1={fir.y + 31} x2="292" y2={fir.y + 31}
            stroke={LINE} strokeWidth="1.5" strokeDasharray="3 3"
          />
          <circle cx="296" cy={fir.y + 31} r="3.5" fill={LINE} />
        </g>
      ))}

      <text x="16" y="292" fontSize="11" fill={CONFLICT_DEEP} fontWeight="500">
        No column joins these rows. Three people.
      </text>

      {/* ------------------------------------------------------ the divider */}
      <line x1="350" y1="30" x2="350" y2="272"
            stroke={LINE} strokeWidth="1" strokeDasharray="2 5" />
      <rect x="316" y="138" width="68" height="22" rx="11"
            fill={SUNKEN} stroke={LINE} />
      <text x="350" y="153" fontSize="10" fontWeight="600" fill={INK2}
            textAnchor="middle" letterSpacing="0.6">
        LAYERS 1 to 7
      </text>

      {/* --------------------------------------------- right, after SUTRA */}
      <text x="404" y="20" fontSize="11" fontWeight="600" fill={RESOLVED_DEEP}
            letterSpacing="1.2">
        AFTER RESOLUTION
      </text>

      {/* Edges from the resolved node back to each case. */}
      {FIRS.map((fir) => (
        <path
          key={`edge-${fir.crime}`}
          d={`M 470 150 C 440 150, 430 ${fir.y + 31}, 412 ${fir.y + 31}`}
          fill="none" stroke={RESOLVED_MID} strokeWidth="1.75"
        />
      ))}
      {FIRS.map((fir) => (
        <circle key={`dot-${fir.crime}`} cx="408" cy={fir.y + 31} r="4"
                fill={RESOLVED_MID} />
      ))}

      <rect x="470" y="106" width="214" height="88" rx="3"
            fill={RESOLVED_TINT} stroke={RESOLVED_MID} strokeWidth="1.5" />
      <text x="486" y="128" fontSize="10" fill={RESOLVED_DEEP}
            className="gapfig__mono" letterSpacing="0.5">
        R000412
      </text>
      <text x="486" y="150" fontSize="15" fontWeight="600" fill={INK}>
        One person
      </text>
      <text x="486" y="168" fontSize="11" fill={INK2}>
        3 records, 3 cases, 2 scripts
      </text>
      {/* No figure here. This diagram is schematic and the identity in it is
          drawn, not measured, so a confidence printed on it would be invented.
          Every real number lives on a screen that reads it from JSON. */}
      <text x="486" y="184" fontSize="10" fill={RESOLVED_DEEP}
            className="gapfig__mono">
        merged in the automatic band
      </text>

      <text x="404" y="292" fontSize="11" fill={RESOLVED_DEEP} fontWeight="500">
        One identity. Two co offender links recovered.
      </text>

      {/* The entity SUTRA adds, named. */}
      <text x="470" y="216" fontSize="9.5" fill={NAVY} className="gapfig__mono">
        ResolvedIdentity, the table SUTRA adds
      </text>
    </svg>
  )
}
