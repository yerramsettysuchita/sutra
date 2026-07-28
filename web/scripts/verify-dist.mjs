/**
 * Verifies the built bundle before it is allowed near Catalyst.
 *
 * Three failures this catches, all of which look fine on localhost and break
 * only once deployed.
 *
 * 1. Missing corpus reports. The page renders its empty state on the live URL.
 *
 * 2. An external host reference. Catalyst serves under a strict CSP that
 *    blocks other origins, so a surviving Google Fonts link means the
 *    government portal renders in Times New Roman. Vendored fonts make this
 *    unlikely, but "unlikely" is not a build gate.
 *
 * 3. Missing font files, which produces the same symptom by a different route.
 *
 * On external hosts the distinction that matters is a request against a
 * string. A CSP blocks fetches, not text. React's minified build embeds
 * documentation URLs in error paths and those are harmless, so this fails on
 * anything that would issue a request and merely reports the rest.
 *
 *   node scripts/verify-dist.mjs
 */

import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs'
import { resolve, dirname, extname, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const DIST = resolve(here, '..', 'dist')

const REQUIRED_REPORTS = ['manifest.json', 'corpus_stats.json', 'blocking_report.json']
/** Written by scripts/export_web.py. Without these the application renders its
 *  not built panels on a live URL, which is worse than failing here. */
const REQUIRED_FEEDS = [
  'eval.json',
  'routing.json',
  'identities.json',
  'network.json',
  'cases.json',
  'profiles.json',
  'hotspots.json',
  'runlog.json',
]
const EXPECTED_FONTS = 8
const TEXT_EXTENSIONS = new Set(['.html', '.js', '.css', '.mjs'])

/** Any occurrence fails. These hosts serve assets and have no business here. */
const FORBIDDEN_HOSTS = [
  'fonts.googleapis.com',
  'fonts.gstatic.com',
  'googleapis.com',
  'gstatic.com',
  'cdn.jsdelivr.net',
  'unpkg.com',
  'cdnjs.cloudflare.com',
  'bootstrapcdn.com',
  'ajax.googleapis.com',
]

/** Constructs that issue a network request at load time. Any match fails. */
const REQUEST_PATTERNS = [
  { label: 'stylesheet link to an external host', re: /<link[^>]+href=["']https?:\/\//gi },
  { label: 'script tag from an external host', re: /<script[^>]+src=["']https?:\/\//gi },
  { label: 'img from an external host', re: /<img[^>]+src=["']https?:\/\//gi },
  { label: 'css @import from an external host', re: /@import\s+(url\()?\s*["']?https?:\/\//gi },
  { label: 'css url() to an external host', re: /url\(\s*["']?https?:\/\//gi },
  { label: 'preload or preconnect to an external host', re: /rel=["'](?:preload|preconnect|dns-prefetch)["'][^>]*href=["']https?:\/\//gi },
]

const failures = []
const notes = []

function walk(dir) {
  const out = []
  for (const entry of readdirSync(dir)) {
    const full = resolve(dir, entry)
    if (statSync(full).isDirectory()) out.push(...walk(full))
    else out.push(full)
  }
  return out
}

if (!existsSync(DIST)) {
  console.error('dist not found. Run: npm run build')
  process.exit(1)
}

const files = walk(DIST)
const rel = (f) => relative(DIST, f).replace(/\\/g, '/')

/* ------------------------------------------------------------- structure */

if (!existsSync(resolve(DIST, 'index.html'))) {
  failures.push('index.html is missing from dist')
}

for (const report of REQUIRED_REPORTS) {
  const path = resolve(DIST, 'corpus', report)
  if (!existsSync(path)) {
    failures.push(
      `dist/corpus/${report} is missing, the deployed page would render empty. ` +
        `Run: npm run sync-corpus`,
    )
    continue
  }
  try {
    const parsed = JSON.parse(readFileSync(path, 'utf-8'))
    if (!parsed || typeof parsed !== 'object') throw new Error('not an object')
  } catch (error) {
    failures.push(`dist/corpus/${report} is not valid JSON, ${error.message}`)
  }
}

for (const feed of REQUIRED_FEEDS) {
  const path = resolve(DIST, 'data', feed)
  if (!existsSync(path)) {
    failures.push(
      `dist/data/${feed} is missing, screens would fall back to their not built ` +
        `state on the live URL. Run: python scripts/export_web.py`,
    )
    continue
  }
  try {
    JSON.parse(readFileSync(path, 'utf-8'))
  } catch (error) {
    failures.push(`dist/data/${feed} is not valid JSON, ${error.message}`)
  }
}

const fonts = files.filter((f) => f.endsWith('.woff2'))
if (fonts.length < EXPECTED_FONTS) {
  failures.push(
    `expected ${EXPECTED_FONTS} woff2 files in dist, found ${fonts.length}. ` +
      `Run: python scripts/vendor_fonts.py`,
  )
}

/* ---------------------------------------------------------- external hosts */

for (const file of files) {
  if (!TEXT_EXTENSIONS.has(extname(file))) continue
  const content = readFileSync(file, 'utf-8')

  for (const host of FORBIDDEN_HOSTS) {
    if (content.includes(host)) {
      failures.push(`${rel(file)} references ${host}, which the Catalyst CSP blocks`)
    }
  }

  for (const { label, re } of REQUEST_PATTERNS) {
    const matches = content.match(re)
    if (matches) {
      failures.push(`${rel(file)} contains a ${label}, ${matches.length} occurrence(s)`)
    }
  }

  // Everything else that merely looks like a URL. Reported, never fatal.
  for (const match of content.matchAll(/https?:\/\/[a-z0-9.-]+/gi)) {
    const url = match[0]
    if (url.includes('localhost') || url.includes('127.0.0.1')) continue
    if (FORBIDDEN_HOSTS.some((h) => url.includes(h))) continue
    notes.push(`${rel(file)}  ${url}`)
  }
}

/* -------------------------------------------------------------- reporting */

console.log('verify dist, ready for Catalyst')
console.log()
console.log(`  files            ${files.length}`)
console.log(`  fonts            ${fonts.length} woff2`)
console.log(`  corpus reports   ${REQUIRED_REPORTS.length} expected`)
const bytes = files.reduce((sum, f) => sum + statSync(f).size, 0)
console.log(`  total size       ${(bytes / 1024).toFixed(0)} KB`)

if (notes.length > 0) {
  const unique = [...new Set(notes)]
  console.log()
  console.log(`  ${unique.length} URL string(s) present, none of them a request:`)
  for (const note of unique.slice(0, 10)) console.log(`    note  ${note}`)
  if (unique.length > 10) console.log(`    note  and ${unique.length - 10} more`)
}

console.log()
if (failures.length > 0) {
  console.error(`REJECTED, ${failures.length} problem(s)`)
  console.error()
  for (const failure of failures) console.error(`  ${failure}`)
  console.error()
  process.exit(1)
}
console.log('  no external host is requested anywhere in the bundle')
console.log('  corpus reports present and parseable')
console.log()
console.log('accepted, safe to package')
