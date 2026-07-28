/**
 * Server side smoke render of every screen against the real engine output.
 *
 * A typecheck proves the shapes line up. It does not prove the tree survives
 * contact with the actual data, where a missing key or an empty array still
 * reaches a `.toFixed` at runtime. This renders each screen to a string with
 * the real files and fails loudly if anything throws.
 *
 * Not a substitute for a browser. It cannot see layout, colour or fonts. It
 * catches the class of failure that ships as a blank page.
 *
 *   node scripts/smoke-render.mjs
 */

import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { renderToString } from 'react-dom/server'
import { createElement } from 'react'

const here = dirname(fileURLToPath(import.meta.url))
const PUBLIC = resolve(here, '..', 'public')

function read(relative) {
  try {
    return JSON.parse(readFileSync(resolve(PUBLIC, relative), 'utf-8'))
  } catch {
    return null
  }
}

const manifest = read('corpus/manifest.json')
const corpus = read('corpus/corpus_stats.json')
const blocking = read('corpus/blocking_report.json')
const evaluation = read('data/eval.json')
const routing = read('data/routing.json')
const identities = read('data/identities.json')
const network = read('data/network.json')
const runlog = read('data/runlog.json')

if (!manifest || !corpus) {
  console.error('no corpus reports found, run: make gen && make stats')
  process.exit(1)
}

const cases = read('data/cases.json')
const profiles = read('data/profiles.json')
const reconciliation = read('data/reconciliation.json')
const hotspots = read('data/hotspots.json')
const scale = read('data/scale.json')
const questions = read('data/questions.json')
const persons = read('data/persons.json')

const full = {
  manifest, corpus, blocking, evaluation, routing, identities, network,
  cases, profiles, reconciliation, hotspots, scale, questions, persons, runlog,
}
// Every downstream feed absent, which is what an evaluator sees after only
// `make gen`. Each screen must degrade rather than throw.
const bare = {
  manifest, corpus,
  blocking: null, evaluation: null, routing: null,
  identities: null, network: null, cases: null, profiles: null,
  reconciliation: null, hotspots: null, scale: null, questions: null,
  persons: null, runlog: null,
}

const SCREENS = [
  ['CorpusAudit', 'screens/CorpusAudit.tsx'],
  ['Evaluation', 'screens/Evaluation.tsx'],
  ['ReviewQueue', 'screens/ReviewQueue.tsx'],
  ['Network', 'screens/Network.tsx'],
  ['Cases', 'screens/Cases.tsx'],
  ['Hotspots', 'screens/Hotspots.tsx'],
  ['Ask', 'screens/Ask.tsx'],
  ['AuditTrail', 'screens/AuditTrail.tsx'],
  ['Status', 'screens/Status.tsx'],
]

const server = await createServer({
  root: resolve(here, '..'),
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'error',
})

let failed = false

const { LanguageProvider } = await server.ssrLoadModule('/src/i18n/useLanguage.tsx')
const { DecisionProvider } = await server.ssrLoadModule(
  '/src/decisions/useDecisions.tsx')
const { ScopeProvider } = await server.ssrLoadModule('/src/scope/useScope.tsx')

async function html(name, path, reports, language) {
  const mod = await server.ssrLoadModule(`/src/${path}`)
  const component = mod[name]
  if (!component) throw new Error(`${name} is not exported from ${path}`)
  return renderToString(
    createElement(
      LanguageProvider,
      { defaultLanguage: language },
      createElement(component, { reports }),
    ),
  )
}

/**
 * The same screen with a decision already recorded, under a named role.
 *
 * The unscoped render only ever exercises the empty decision log and the
 * default role. Neither of those is the interesting case: the outcome line on a
 * queue row, the reverse control on the audit trail, and the read only notice
 * for the investigating officer are all code paths that only run once somebody
 * has acted or once the role changes.
 */
async function htmlAs(name, path, reports, { role, decisions }) {
  const mod = await server.ssrLoadModule(`/src/${path}`)
  const component = mod[name]
  return renderToString(
    createElement(
      LanguageProvider,
      { defaultLanguage: 'en' },
      createElement(
        ScopeProvider,
        { districts: ['Bengaluru Urban'], defaultRole: role },
        createElement(
          DecisionProvider,
          { initial: decisions },
          createElement(component, { reports }),
        ),
      ),
    ),
  )
}

async function render(name, path, reports, label) {
  try {
    const markup = await html(name, path, reports, 'en')
    if (markup.includes('NaN') || markup.includes('undefined')) {
      console.error(`  FAIL  ${name} ${label}, output contains NaN or undefined`)
      failed = true
      return
    }
    const digits = (markup.match(/\d/g) ?? []).length
    console.log(`  ok    ${name} ${label}, ${markup.length} chars, ${digits} digits`)
  } catch (error) {
    console.error(`  FAIL  ${name} ${label}`)
    console.error(String(error?.stack ?? error).split('\n').slice(0, 6).join('\n'))
    failed = true
  }
}

/**
 * The Kannada interface, checked for the two things that could go wrong.
 *
 * One, the toggle has to actually reach the chrome, so Kannada glyphs must be
 * present. Two, and this is the one that would matter in a police office, no
 * figure may change. Every run of digits in the English render must appear in
 * the Kannada render, in the same order and the same number of times. A crime
 * number, an AMID or a metric that shifted under translation would be a wrong
 * answer rendered confidently.
 */
const KANNADA = /[ಀ-೿]/

function digitRuns(markup) {
  return (markup.replace(/<[^>]*>/g, ' ').match(/\d[\d,.:-]*/g) ?? []).join('|')
}

async function renderKannada(name, path, reports) {
  try {
    const english = await html(name, path, reports, 'en')
    const kannada = await html(name, path, reports, 'kn')

    if (!KANNADA.test(kannada)) {
      console.error(`  FAIL  ${name}, no Kannada reached the markup`)
      failed = true
      return
    }
    const before = digitRuns(english)
    const after = digitRuns(kannada)
    if (before !== after) {
      console.error(`  FAIL  ${name}, a figure changed under translation`)
      failed = true
      return
    }
    const glyphs = (kannada.match(/[ಀ-೿]/g) ?? []).length
    console.log(`  ok    ${name}, ${glyphs} Kannada glyphs, every figure identical`)
  } catch (error) {
    console.error(`  FAIL  ${name} (kannada)`)
    console.error(String(error?.stack ?? error).split('\n').slice(0, 6).join('\n'))
    failed = true
  }
}

console.log('smoke render, every screen')
console.log()
console.log('with the full export')
for (const [name, path] of SCREENS) await render(name, path, full, '')
console.log()
console.log('with only the corpus, every downstream feed missing')
for (const [name, path] of SCREENS) await render(name, path, bare, '(degraded)')
console.log()
console.log('in Kannada, with every figure required to be unchanged')
for (const [name, path] of SCREENS) await renderKannada(name, path, full)

/**
 * The same screens under a jurisdiction scope.
 *
 * The scope filter projects six feeds and recomputes the counts derived from
 * them. Every one of those projections is a place a null or an empty array can
 * reach a `.toFixed`, and none of it is exercised by the unscoped render. So
 * render every screen again with a real district selected, and require that
 * the filter actually removed something, because a filter that silently keeps
 * everything would pass a render check while doing nothing.
 */
const { applyScope } = await server.ssrLoadModule('/src/scope/filter.ts')

const districts = [...new Set((hotspots?.districts ?? []).map((d) => d.district))]
const district = districts[0] ?? null

console.log()
console.log(`scoped to one district, ${district ?? 'none available'}`)
if (!district) {
  console.log('  note  no district in the export, scope filter not exercised')
} else {
  const { reports: scoped, effect } = applyScope(full, district)
  for (const [name, path] of SCREENS) {
    await render(name, path, scoped, `(scoped to ${district})`)
  }
  const shrank =
    effect.identities.after < effect.identities.before ||
    effect.cases.after < effect.cases.before ||
    effect.edges.after < effect.edges.before
  if (!shrank) {
    console.error('  FAIL  the scope filter removed nothing, so it is not filtering')
    failed = true
  } else {
    console.log(
      `  ok    filter removed something: identities ${effect.identities.before} to ` +
        `${effect.identities.after}, cases ${effect.cases.before} to ${effect.cases.after}, ` +
        `edges ${effect.edges.before} to ${effect.edges.after}, ` +
        `${effect.edges.cutAtBoundary} cut at the boundary`,
    )
  }
}

/**
 * The decision layer, rendered.
 *
 * check-decisions.mjs proves the log behaves. This proves the screens survive
 * contact with it, which is a different failure and the one that ships as a
 * blank page.
 */
const firstPair = routing?.pairs?.[0]
console.log()
console.log('with a decision recorded, per role')
if (!firstPair) {
  console.log('  note  no review band pairs exported, decision paths not exercised')
} else {
  const decisions = [
    {
      pair_id: firstPair.pair_id,
      amid_left: firstPair.left.amid,
      amid_right: firstPair.right.amid,
      action: 'merge',
      role: 'operator',
      role_label: 'Records operator',
      district: null,
      at: '2026-07-29T10:00:00.000Z',
      probability: firstPair.probability,
    },
  ]
  for (const role of ['operator', 'io', 'reviewer', 'analyst']) {
    for (const [name, path] of [['ReviewQueue', 'screens/ReviewQueue.tsx'],
                                ['AuditTrail', 'screens/AuditTrail.tsx'],
                                ['Status', 'screens/Status.tsx']]) {
      try {
        const markup = await htmlAs(name, path, full, { role, decisions })
        if (markup.includes('NaN') || markup.includes('undefined')) {
          console.error(`  FAIL  ${name} as ${role}, NaN or undefined in output`)
          failed = true
          continue
        }
        console.log(`  ok    ${name} as ${role}, ${markup.length} chars`)
      } catch (error) {
        console.error(`  FAIL  ${name} as ${role}`)
        console.error(String(error?.stack ?? error).slice(0, 400))
        failed = true
      }
    }
  }

  // The permission difference has to be visible in the markup, not merely
  // true in the model. A disabled Merge button is the whole point of the role.
  const asOperator = await htmlAs('ReviewQueue', 'screens/ReviewQueue.tsx', full,
                                  { role: 'operator', decisions: [] })
  const asOfficer = await htmlAs('ReviewQueue', 'screens/ReviewQueue.tsx', full,
                                 { role: 'io', decisions: [] })
  if (asOfficer.includes('read only for your role') &&
      !asOperator.includes('read only for your role')) {
    console.log('  ok    the officer sees the read only notice and the operator does not')
  } else {
    console.error('  FAIL  the read only notice does not distinguish the roles')
    failed = true
  }

  const reviewerAudit = await htmlAs('AuditTrail', 'screens/AuditTrail.tsx', full,
                                     { role: 'reviewer', decisions })
  const operatorAudit = await htmlAs('AuditTrail', 'screens/AuditTrail.tsx', full,
                                     { role: 'operator', decisions })
  if (reviewerAudit.includes('Reverse') && !operatorAudit.includes('>Reverse<')) {
    console.log('  ok    only the reviewer is offered the reverse control')
  } else {
    console.error('  FAIL  the reverse control is not restricted to the reviewer')
    failed = true
  }

  const emptyAudit = await htmlAs('AuditTrail', 'screens/AuditTrail.tsx', full,
                                  { role: 'reviewer', decisions: [] })
  if (emptyAudit.includes('No decisions have been taken')) {
    console.log('  ok    an empty log says so rather than showing an empty table')
  } else {
    console.error('  FAIL  the empty decision log does not explain itself')
    failed = true
  }
}

await server.close()
process.exit(failed ? 1 : 0)
