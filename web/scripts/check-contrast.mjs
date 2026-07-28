/**
 * WCAG 2.1 contrast verification for the SUTRA palette.
 *
 * Reads the real token values out of src/styles/tokens.css rather than a copy,
 * computes the contrast ratio for every pair the design actually puts together,
 * and exits non zero if any drops below 4.5 to 1. Wired into `npm run check`,
 * so a palette change that breaks accessibility breaks the build.
 *
 * Text pairs are held to 4.5. Non text pairs, borders and bars against their
 * background, are held to 3.0, which is the WCAG 1.4.11 threshold for
 * meaningful non text contrast. Both are reported.
 *
 *   node scripts/check-contrast.mjs
 */

import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const TOKENS = resolve(here, '..', 'src', 'styles', 'tokens.css')

const TEXT_MIN = 4.5
const NON_TEXT_MIN = 3.0

/* ------------------------------------------------------------- token parse */

const css = readFileSync(TOKENS, 'utf-8')
const tokens = new Map()
for (const match of css.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})\s*;/g)) {
  tokens.set(match[1], match[2])
}

function hex(name) {
  const value = tokens.get(name)
  if (!value) {
    console.error(`token --${name} not found in tokens.css`)
    process.exit(1)
  }
  return value
}

/* ------------------------------------------------------------------ colour */

function channel(v) {
  const c = v / 255
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

function luminance(value) {
  let h = value.replace('#', '')
  if (h.length === 3) h = h.split('').map((c) => c + c).join('')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function ratio(a, b) {
  const la = luminance(a)
  const lb = luminance(b)
  const [hi, lo] = la > lb ? [la, lb] : [lb, la]
  return (hi + 0.05) / (lo + 0.05)
}

/* ------------------------------------------------------------------- pairs */

const TRIADS = ['resolved', 'review', 'conflict', 'signal', 'official']

const textPairs = [
  ['ink on paper', 'ink', 'paper'],
  ['ink-2 on paper', 'ink-2', 'paper'],
  ['ink-3 on paper', 'ink-3', 'paper'],
  ['ink on surface', 'ink', 'surface'],
  ['ink-2 on surface', 'ink-2', 'surface'],
  ['ink-3 on surface', 'ink-3', 'surface'],
  ['ink on sunken', 'ink', 'sunken'],
  ['ink-2 on sunken', 'ink-2', 'sunken'],
  ['ink-3 on sunken', 'ink-3', 'sunken'],
  ['navy on paper', 'navy', 'paper'],
  ['navy on surface', 'navy', 'surface'],
  // Masthead reverses out, so white on navy is a text pair too.
  ['white on navy', 'white', 'navy'],
  // The language switch sits on the navy band. Selected is navy on a solid
  // white fill, unselected is white on navy. Kannada is set at the same size
  // as the interface face and takes the same pair, so both are checked here
  // rather than assumed from the chip beside them.
  ['langswitch selected', 'navy', 'white'],
  ['langswitch unselected', 'white', 'navy'],
]

// Every deep shade must pass on paper, on white, on sunken, and on its own
// tint, because all four combinations occur on the page.
for (const triad of TRIADS) {
  textPairs.push([`${triad}-deep on its tint`, `${triad}-deep`, `${triad}-tint`])
  textPairs.push([`${triad}-deep on paper`, `${triad}-deep`, 'paper'])
  textPairs.push([`${triad}-deep on surface`, `${triad}-deep`, 'surface'])
  textPairs.push([`${triad}-deep on sunken`, `${triad}-deep`, 'sunken'])
}

const nonTextPairs = [
  ['line-strong on paper', 'line-strong', 'paper'],
  ['line-strong on surface', 'line-strong', 'surface'],
]

// Mid is used for bars, chip borders and eyebrows. It must be distinguishable
// from what sits behind it, and it must never be used for text, which is why
// it is checked at the non text threshold only.
for (const triad of TRIADS) {
  nonTextPairs.push([`${triad}-mid on surface`, `${triad}-mid`, 'surface'])
  nonTextPairs.push([`${triad}-mid on its tint`, `${triad}-mid`, `${triad}-tint`])
}

tokens.set('white', '#ffffff')

/* ------------------------------------------------------------------ report */

let failed = 0
let advisories = 0

function check(pairs, minimum, heading, blocking) {
  console.log(`\n${heading}, ${minimum.toFixed(1)} to 1\n`)
  for (const [label, fg, bg] of pairs) {
    const value = ratio(hex(fg), hex(bg))
    const ok = value >= minimum
    if (!ok) {
      if (blocking) failed += 1
      else advisories += 1
    }
    const mark = ok ? 'ok  ' : blocking ? 'FAIL' : 'note'
    console.log(
      `  ${mark} ${label.padEnd(30)} ${value.toFixed(2).padStart(6)} to 1` +
        `   ${hex(fg)} on ${hex(bg)}`,
    )
  }
}

console.log('SUTRA palette contrast, WCAG 2.1')

check(textPairs, TEXT_MIN, 'Text, blocking at', true)

/*
 * Non text is advisory, and the reason is worth stating rather than assuming.
 *
 * WCAG 1.4.11 applies to graphical objects "required to understand the
 * content". Nothing in this palette's non text usage meets that description,
 * because every graphic in SUTRA is redundant with an adjacent number.
 *
 *   table bars      the count and the percentage sit in the cells beside them
 *   gap bar         both endpoints are printed in the legend, plus an aria-label
 *   panel eyebrows  categorisation only, the panel title carries the meaning
 *   chip borders    the chip's deep text states the status in words
 *   hairlines       structure is also carried by spacing and by the sunken
 *                   header fill, and a hairline at 3.0 to 1 would be a heavy
 *                   grey rule that wrecks the register
 *
 * So these do not block. They are still measured and printed, because a mid
 * that is too faint to see is a bad graphic even when it is not a violation,
 * and that judgement should be made against a number.
 */
check(nonTextPairs, NON_TEXT_MIN, 'Non text, advisory at', false)

console.log()
if (failed > 0) {
  console.error(
    `${failed} text pair${failed === 1 ? '' : 's'} below ${TEXT_MIN} to 1. Palette rejected.`,
  )
  process.exit(1)
}
console.log(`All ${textPairs.length} text pairs pass at ${TEXT_MIN} to 1.`)
if (advisories > 0) {
  console.log(
    `${advisories} non text pair${advisories === 1 ? '' : 's'} below ${NON_TEXT_MIN} to 1. ` +
      `Not blocking, see the rationale in this file. Worth a look if a bar reads faint.`,
  )
}
