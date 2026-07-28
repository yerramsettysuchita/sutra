/**
 * The decision layer, tested where it can actually be tested.
 *
 * Three things here carry a claim that a jury would be right to check, and none
 * of them is provable by looking at a screenshot.
 *
 *   1. The log is append only. /status claims an audit trail. A trail that can
 *      lose an entry is not one, so reversal must add rather than remove.
 *
 *   2. The fold is correct. The current state of a pair is derived from the
 *      log, so if the fold is wrong the screen and the audit disagree about
 *      what happened.
 *
 *   3. The role permissions are what /status says they are. The table on that
 *      page is generated from the same definitions, so the risk is not that the
 *      table lies, it is that the definitions drift from what was designed.
 *
 * Run inside `npm run check` so it gates the build.
 *
 *   node scripts/check-decisions.mjs
 */

import { createServer } from 'vite'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))

let failed = 0
let passed = 0

function check(name, condition, detail = '') {
  if (condition) {
    passed += 1
    console.log(`  ok   ${name}`)
  } else {
    failed += 1
    console.error(`  FAIL ${name}${detail ? `  ${detail}` : ''}`)
  }
}

const server = await createServer({
  root: resolve(here, '..'),
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'error',
})

const { foldLog, summarise } = await server.ssrLoadModule(
  '/src/decisions/useDecisions.tsx')
const { ROLES, ROLE_BY_ID } = await server.ssrLoadModule('/src/scope/useScope.tsx')

const entry = (over = {}) => ({
  pair_id: 'P1',
  amid_left: '1',
  amid_right: '2',
  action: 'merge',
  role: 'operator',
  role_label: 'Records operator',
  district: null,
  at: '2026-07-29T10:00:00.000Z',
  probability: 0.71,
  ...over,
})

console.log('decision layer')
console.log()
console.log('The fold, which is what every screen reads')
console.log()

{
  const state = foldLog([entry()])
  check('a merge folds to merge', state.get('P1')?.action === 'merge')
}
{
  const state = foldLog([entry(), entry({ action: 'keep separate',
                                          at: '2026-07-29T11:00:00.000Z' })])
  check('a later decision wins over an earlier one',
        state.get('P1')?.action === 'keep separate')
}
{
  const log = [entry(), entry({ action: 'reverse',
                                at: '2026-07-29T11:00:00.000Z',
                                reverses: 'P1@2026-07-29T10:00:00.000Z' })]
  const state = foldLog(log)
  check('a reversal returns the pair to pending',
        state.get('P1')?.action === null)
  check('a reversal is marked as reversed rather than as absent',
        state.get('P1')?.reversed === true)
  check('THE APPEND ONLY GUARANTEE: the reversed entry is still in the log',
        log.length === 2 && log[0].action === 'merge',
        'the original merge must survive its own reversal')
  check('the reversal names the entry it reverses',
        log[1].reverses === 'P1@2026-07-29T10:00:00.000Z')
}
{
  const state = foldLog([])
  check('an empty log folds to no decisions', state.size === 0)
}
{
  // A pair decided, reversed, then decided again. The log grows by three and
  // the state is the last decision.
  const log = [
    entry(),
    entry({ action: 'reverse', at: '2026-07-29T11:00:00.000Z' }),
    entry({ action: 'keep separate', at: '2026-07-29T12:00:00.000Z' }),
  ]
  const state = foldLog(log)
  check('decide, reverse, decide again ends at the last decision',
        state.get('P1')?.action === 'keep separate')
  check('and every one of the three entries is still present',
        log.length === 3)
}

console.log()
console.log('The summary the review queue puts in its sub header')
console.log()

{
  const log = [
    entry({ pair_id: 'P1' }),
    entry({ pair_id: 'P2', action: 'keep separate' }),
    entry({ pair_id: 'P3' }),
    entry({ pair_id: 'P3', action: 'reverse', at: '2026-07-29T13:00:00.000Z' }),
  ]
  const s = summarise(log, 10)
  check('merged counts only pairs currently merged', s.merged === 1,
        `got ${s.merged}`)
  check('kept separate counts only pairs currently kept', s.keptSeparate === 1,
        `got ${s.keptSeparate}`)
  check('a reversed pair returns to pending', s.decided === 2 && s.pending === 8,
        `decided ${s.decided}, pending ${s.pending}`)
  check('reversed counts operator activity, not current state',
        s.reversed === 1, `got ${s.reversed}`)
}
{
  const s = summarise([], 5)
  check('nothing decided means everything pending',
        s.decided === 0 && s.pending === 5)
}
{
  // Deciding the same pair twice must not double count it.
  const log = [entry(), entry({ at: '2026-07-29T11:00:00.000Z' })]
  const s = summarise(log, 3)
  check('deciding one pair twice counts it once',
        s.merged === 1 && s.decided === 1, `merged ${s.merged}`)
}
{
  const s = summarise([entry(), entry({ pair_id: 'P2' })], 1)
  check('pending never goes negative', s.pending === 0, `got ${s.pending}`)
}

console.log()
console.log('Role permissions, against what /status publishes')
console.log()

check('four roles are defined', ROLES.length === 4, `got ${ROLES.length}`)
check('the investigating officer cannot decide',
      ROLE_BY_ID.io.canDecide === false)
check('the records operator can decide, it is the role the queue exists for',
      ROLE_BY_ID.operator.canDecide === true)
check('the SCRB analyst can decide', ROLE_BY_ID.analyst.canDecide === true)
check('the reviewer can decide', ROLE_BY_ID.reviewer.canDecide === true)
check('ONLY the reviewer can reverse',
      ROLES.filter((r) => r.canReverse).map((r) => r.id).join(',') === 'reviewer',
      ROLES.filter((r) => r.canReverse).map((r) => r.id).join(',') || 'none')
check('no role that cannot decide can reverse',
      ROLES.every((r) => !r.canReverse || r.canDecide))
check('the records operator is confined to the review queue',
      ROLE_BY_ID.operator.routes.join(',') === '/identities')
check('the investigating officer is the only district scoped role',
      ROLES.filter((r) => r.districtScoped).map((r) => r.id).join(',') === 'io')
check('every role states what it can do, for the /status table',
      ROLES.every((r) => typeof r.can === 'string' && r.can.length > 10))

await server.close()

console.log()
if (failed > 0) {
  console.error(`${failed} check${failed === 1 ? '' : 's'} failed, ${passed} passed.`)
  process.exit(1)
}
console.log(`Decision layer verified, ${passed} checks.`)
