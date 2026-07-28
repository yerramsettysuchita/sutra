/**
 * Copies the corpus reports into web/public/corpus.
 *
 * Why this exists.
 *
 * The screen previously read the reports through a Vite dev middleware. That
 * middleware is a development server feature and does not exist in a static
 * build, so `npm run build` produced a bundle that fetched /corpus/... and got
 * the SPA fallback HTML back. The page rendered its empty state on the
 * deployed URL while working perfectly on localhost, which is the worst shape
 * a bug can take.
 *
 * Anything under public/ is copied verbatim into dist/ by Vite, so the same
 * path serves in development and in production and the application has one
 * code path rather than two.
 *
 * This runs as `predev` and `prebuild`, and again on change while the dev
 * server is up. It fails loudly rather than letting a blank panel ship.
 *
 *   node scripts/sync-corpus.mjs
 */

import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const SRC = resolve(here, '..', '..', 'data', 'corpus')
const DEST = resolve(here, '..', 'public', 'corpus')

/** Each file, and a top level key that must be present for it to be usable. */
const REQUIRED = [
  { file: 'manifest.json', key: 'counts', produced_by: 'make gen' },
  { file: 'corpus_stats.json', key: 'recoverability', produced_by: 'make stats' },
  { file: 'blocking_report.json', key: 'ceiling', produced_by: 'make block' },
]

export function syncCorpus({ quiet = false } = {}) {
  const log = (line) => {
    if (!quiet) console.log(line)
  }
  const problems = []

  if (!existsSync(SRC)) {
    problems.push(`corpus directory not found at ${SRC}`)
  } else {
    mkdirSync(DEST, { recursive: true })
    for (const { file, key, produced_by } of REQUIRED) {
      const from = resolve(SRC, file)
      if (!existsSync(from)) {
        problems.push(`${file} is missing, produced by: ${produced_by}`)
        continue
      }
      let parsed
      try {
        parsed = JSON.parse(readFileSync(from, 'utf-8'))
      } catch (error) {
        problems.push(`${file} is not valid JSON, ${error.message}`)
        continue
      }
      if (!parsed || typeof parsed !== 'object' || !(key in parsed)) {
        problems.push(
          `${file} has no "${key}" key, so it is stale or truncated. ` +
            `Regenerate with: ${produced_by}`,
        )
        continue
      }
      copyFileSync(from, resolve(DEST, file))
      const size = statSync(from).size
      log(`  ok  ${file.padEnd(22)} ${(size / 1024).toFixed(1).padStart(7)} KB`)
    }
  }

  if (problems.length > 0) {
    const message = [
      '',
      'Corpus reports are missing or unusable, so the build would ship a blank page.',
      '',
      ...problems.map((p) => `  ${p}`),
      '',
      'From the repository root:',
      '',
      '  make gen',
      '  make stats',
      '  make block',
      '',
      'or without make:',
      '',
      '  python -m data.generator.generate --cases 5000',
      '  python -m data.generator.audit',
      '  python -m engine.block.evaluate',
      '',
    ].join('\n')
    throw new Error(message)
  }

  log(`  ->  ${DEST}`)
  return true
}

const invokedDirectly =
  process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))

if (invokedDirectly) {
  console.log('sync corpus reports into web/public/corpus')
  try {
    syncCorpus()
  } catch (error) {
    console.error(error.message)
    process.exit(1)
  }
}
