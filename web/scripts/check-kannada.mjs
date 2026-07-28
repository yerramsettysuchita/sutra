/**
 * Verification for the Kannada interface.
 *
 * Three things could go wrong here and none of them would throw. The type
 * could clip, a figure could be translated, or the font could not be there.
 * All three ship as a page that renders.
 *
 *   1. Line height. Kannada carries matras above and below the baseline and
 *      conjuncts stack two consonants, so a line box tuned for Latin clips the
 *      top of a vowel sign. Every selector that renders translated chrome is
 *      resolved against the real CSS and must reach 1.4.
 *
 *   2. Figures. Nothing numeric may translate. A crime number, an AMID, a
 *      metric or a threshold rendered differently by language would be a wrong
 *      answer shown confidently. Enforced here on the dictionary, and enforced
 *      again on the rendered markup by scripts/smoke-render.mjs, which requires
 *      every digit run to be identical in both languages.
 *
 *   3. The font. Catalyst blocks external hosts, so a missing local woff2 is a
 *      silent fallback to whatever the machine has, which for Kannada is often
 *      nothing at all.
 *
 * Contrast is not rechecked here. Kannada is set in the same tokens as the
 * interface face at the same sizes, so scripts/check-contrast.mjs already
 * covers every pair it can appear in, including the two language buttons on
 * the navy masthead.
 *
 *   node scripts/check-kannada.mjs
 */

import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const STYLES = resolve(here, '..', 'src', 'styles')
const FONTS = resolve(here, '..', 'public', 'fonts')
const STRINGS = resolve(here, '..', 'src', 'i18n', 'strings.ts')

const MIN_LEADING = 1.4

let failed = 0
const say = (ok, text) => {
  if (!ok) failed += 1
  console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${text}`)
}

/* --------------------------------------------------------------- css parse */

const css = readdirSync(STYLES)
  .filter((f) => f.endsWith('.css') && f !== 'print.css')
  .map((f) => readFileSync(resolve(STYLES, f), 'utf-8'))
  .join('\n')

const tokens = new Map()
for (const match of css.matchAll(/--(leading-[a-z]+):\s*([\d.]+)\s*;/g)) {
  tokens.set(match[1], Number(match[2]))
}

/**
 * selector -> line-height, for every rule in the sheet. A rule listing several
 * selectors records the value against each of them, which is what the cascade
 * does.
 */
function leadingBySelector(source) {
  const found = new Map()
  for (const match of source.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const declaration = /line-height:\s*([^;]+);/.exec(match[2])
    if (!declaration) continue
    let raw = declaration[1].trim()
    const variable = /var\(\s*--([a-z-]+)\s*\)/.exec(raw)
    const value = variable ? tokens.get(variable[1]) : Number(raw)
    if (!Number.isFinite(value)) continue
    for (const selector of match[1].split(',')) {
      found.set(selector.trim(), value)
    }
  }
  return found
}

const all = leadingBySelector(css)

/** The declared value for a selector when the interface is in Kannada. */
function kannadaLeading(selector) {
  const override = all.get(`html[data-lang='kn'] ${selector}`)
  if (override !== undefined) return override
  const base = all.get(selector)
  if (base !== undefined) return base
  return all.get(`html[data-lang='kn'] body`) ?? tokens.get('leading-body') ?? 0
}

/*
 * Every selector below renders a string that passes through the dictionary.
 * If a screen starts translating something new, add it here, because a
 * selector that is not listed is not checked.
 */
const TRANSLATED = [
  '.panel__title',
  '.subhead__title',
  '.rail__label',
  '.rail__hint',
  '.metric__label',
  '.table th',
  '.pill',
  '.provenance__key',
  '.audit-strip__key',
  '.langswitch__btn',
  '.btn',
  '.filter',
]

console.log('Kannada interface checks')
console.log()
console.log(`Line height, at least ${MIN_LEADING} where translated text renders`)
console.log()
for (const selector of TRANSLATED) {
  const value = kannadaLeading(selector)
  say(value >= MIN_LEADING,
      `${selector.padEnd(24)} ${value.toFixed(2)}`)
}

/* -------------------------------------------------------------- dictionary */

console.log()
console.log('Dictionary')
console.log()

const strings = readFileSync(STRINGS, 'utf-8')
const body = strings.split('export const KN')[1]?.split('\n}')[0] ?? ''
const entries = [...body.matchAll(/^\s*'?([^':\n]+)'?:\s*'([^']*)',/gm)]
  .map((m) => [m[1].trim(), m[2]])

say(entries.length > 80, `${entries.length} entries`)

const KANNADA = /[ಀ-೿]/
/*
 * Digits are allowed in a chrome label, because a layer number and a threshold
 * are part of the words. What is not allowed is for a digit to come out
 * different, whether renumbered, reordered, dropped, or rendered in Kannada
 * numerals. So the rule is not a ban, it is equality: the digit run of the
 * translation must be the digit run of the English, exactly.
 *
 * Kannada has its own digit forms, ೦ to ೯, and they are readable. They are
 * still refused here. A crime number half in one numeral system is not a crime
 * number anybody can type back into a search box.
 */
const digitsOf = (text) => (text.match(/\d/g) ?? []).join('')
const KANNADA_DIGITS = /[೦-೯]/

const renumbered = entries.filter(
  ([key, value]) => digitsOf(key) !== digitsOf(value) || KANNADA_DIGITS.test(value),
)
say(renumbered.length === 0,
    renumbered.length === 0
      ? 'every digit survives translation unchanged, in Latin numerals'
      : `digits changed: ${renumbered.map(([k]) => k).join(', ')}`)

const empty = entries.filter(([, value]) => !value.trim())
say(empty.length === 0,
    empty.length === 0 ? 'no empty translation' : `empty: ${empty.map(([k]) => k).join(', ')}`)

const notKannada = entries.filter(([, value]) => !KANNADA.test(value))
say(notKannada.length === 0,
    notKannada.length === 0
      ? 'every value is in the Kannada block'
      : `not Kannada: ${notKannada.map(([k]) => k).join(', ')}`)

/* -------------------------------------------------------------------- font */

console.log()
console.log('Font')
console.log()

say(/font-family:\s*'Noto Sans Kannada'/.test(css),
    "Noto Sans Kannada is declared as a local face")
say(/--font-kannada:[^;]*Noto Sans Kannada/.test(css),
    '--font-kannada names it')
say(/html\[data-lang='kn'\][^{]*body[^{]*\{[^}]*Noto Sans Kannada/s.test(css),
    'the Kannada interface stack falls through to it')

const woff2 = existsSync(FONTS)
  ? readdirSync(FONTS).filter((f) => /noto.*kannada/i.test(f) && f.endsWith('.woff2'))
  : []
say(woff2.length > 0,
    woff2.length ? `vendored, ${woff2.join(', ')}` : 'no vendored woff2 found in public/fonts')

say(!/fonts\.googleapis|fonts\.gstatic/.test(css),
    'no external font host, which Catalyst would block anyway')

console.log()
if (failed > 0) {
  console.error(`${failed} check${failed === 1 ? '' : 's'} failed.`)
  process.exit(1)
}
console.log('Kannada interface verified.')
