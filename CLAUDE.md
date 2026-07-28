# SUTRA, working agreement

Identity resolution for the KSP crime record. Datathon 2026, problem statement 01.

The thesis and the engineering plan live in [docs/architecture.md](docs/architecture.md).
Every non obvious choice is an ADR in [docs/decisions.md](docs/decisions.md).
What we refuse to build is in [docs/ethics.md](docs/ethics.md).

## Design direction

Government intelligence portal. SUTRA is read in daylight, in a police office,
on a projector, and printed. Light, colourful and considered, with dark text
that is effortless to read.

**The dark instrument register is withdrawn.** It is not an alternate theme and
it is not coming back. The palette below is not an inversion of it, which is why
the page is a warm off white rather than pure white and the panels are the
white.

### Palette

Surfaces.

| Token | Value | Use |
|---|---|---|
| `--paper` | `#FBFAF7` | page, warm off white, never pure white |
| `--surface` | `#FFFFFF` | panels |
| `--sunken` | `#F4F2EE` | table headers, recessed wells, code |
| `--line` | `#E4E1DA` | hairlines |
| `--line-strong` | `#CFCBC1` | panel borders, table rules |

Text, measured against paper.

| Token | Value | Ratio |
|---|---|---|
| `--ink` | `#14171C` | 17.21 to 1 |
| `--ink-2` | `#464D55` | 8.20 to 1 |
| `--ink-3` | `#656C75` | 5.09 to 1, never go lighter |

Brand. `--navy` `#16305C`, 12.49 to 1. Masthead and primary actions.

Semantic triads. Every colour has tint, mid and deep.

| Meaning | Tint | Mid | Deep |
|---|---|---|---|
| resolved | `#E4F3EA` | `#2E9E6B` | `#0F5D3C` |
| review | `#FBF1DE` | `#B57F14` | `#7A4E06` |
| conflict | `#FBEBE9` | `#D9534A` | `#8C2018` |
| signal | `#E8EDFA` | `#4E6FD9` | `#22357F` |
| official | `#F3EFE1` | `#A8913F` | `#6B5A25` |

Roles within a triad are fixed. **Tint is background only. Mid is fills, bars
and borders only. Deep is the only shade text is ever set in.** Every deep on
its own tint is above 5.8 to 1.

Meaning is fixed. Never use a colour outside it.

- **resolved** something recovered that was invisible before
- **review** a human decision is required
- **conflict** a constraint violation or a wrong result
- **signal** interactive, queries, links, navigation
- **official** provenance, seed, source file, timestamp, attribution

### How colour is applied

This is what makes the page colourful without noise.

- Panel eyebrows carry colour. Panel backgrounds stay white
- Metric readouts are set in their triad's deep shade
- Bars, sparklines and comparison viz use mid at full saturation
- Status chips are tint background, deep text, 1px mid border
- Tables get a sunken header row and one hairline per row, no zebra
- Never colour a large area. Never place two saturated fills adjacent

The masthead is the single exception, a solid navy band, because a government
portal identifies its issuing authority first.

### Government portal framing

- Masthead in navy carrying the Karnataka State Police attribution above the
  SUTRA wordmark, with State Crime Records Bureau beneath it
- A provenance bar directly under the masthead in official tint, carrying seed,
  corpus timestamp, blocking timestamp and every file read. A compact copy stays
  pinned at the bottom
- Every panel keeps its one line explaining what the number means and why it
  matters. That framing is the strongest thing on the page

### Type

| Role | Family |
|---|---|
| Display | Bricolage Grotesque, variable, optical size axis |
| Interface | Inter Tight |
| Kannada | Noto Sans Kannada, matched optically to Inter Tight |
| Data | JetBrains Mono |

Every number in this product is monospaced. Identifiers, crime numbers, SQL
fragments and file paths all take JetBrains Mono. Display tracking is tight,
about `-0.02em`. Data tracking stays at `0`.

All four are vendored as local woff2 with `font-display: swap`, under
`web/public/fonts`. Catalyst blocks external hosts, so Google Fonts fails on
deploy. Regenerate with `python scripts/vendor_fonts.py`.

### Print

Government readers print. `web/src/styles/print.css` is written for paper, not
derived from the screen. White background, hairlines survive, colour chips
degrade to labelled text with a role prefix, page breaks land between panels
never inside one, table headers repeat across pages, and link targets are
printed after the link text.

### Depth

On paper, elevation is a hairline and a very slight lift. No drop shadows, no
glassmorphism, no gradient meshes.

Three dimensions only where the data is genuinely dimensional. The identity
graph and the space time cube qualify. Nothing else does.

### Motion

Purposeful only. The resolution collapse animation is the single moment of drama
and it runs under 1.2 seconds. Everything else is 120 to 180ms ease out. All of
it wrapped in `prefers-reduced-motion`.

### Density

High. Information density reads as capability. Small type, tight leading,
generous negative space around dense blocks rather than inside them. Never
centre body text.

### Copy

No dashes and no colons mid sentence. Sentence case throughout. Plain verbs,
active voice. No exclamation marks, no emoji, no marketing adjectives. The
product sounds like a competent colleague.

### Accessibility, non negotiable

Semantic HTML. Contrast at least 4.5 to 1 on all text. Focus rings at 2px in
signal mid with 2px offset, never removed. Full keyboard reachability. Status
never carried by colour alone, always paired with a word. The 3D graph needs a
table equivalent behind a toggle. Table captions and aria labels throughout.

Verified in code. `web/scripts/check-contrast.mjs` parses the real token file,
computes every pair the design uses, and fails the build below 4.5 to 1 on text.
It runs in `npm run check`.

Written from the first commit, never retrofitted.

## Engineering rules

Resolution is a nightly batch job. The deployed surface is read only. Nothing
heavy ships into a Catalyst function. See ADR 002.

Catalyst services only. LLM and embeddings go to QuickML, speech to Zia, storage
to Data Store or Stratus, auth to Catalyst Authentication, scheduling to Job
Scheduling. Python libraries running in our own process are fine. Hosted third
party APIs are not.

`CasteID`, `ReligionID` and `OccupationID` are never model features. Enforced by
`engine/policy.py`, which raises rather than warns.

Every engine module gets tests. Conventional commits.

The deployed Catalyst URL is https://sutra-gfrnnril.onslate.in/ and never
changes. Never create a new Catalyst app, always overwrite.

Git is handled by the user. Never run git commands.

## Reporting

Report failure numbers honestly. The false merge rate and the refusal rate are
the most valuable figures in the project and are never rounded in our favour.

When a measurement contradicts a number we published earlier, the new number
wins and the old one is named as superseded rather than quietly replaced.
