import { useEffect, useState } from 'react'
import type {
  BlockingReport,
  CasesFeed,
  CorpusStats,
  EvalReport,
  IdentityFeed,
  Manifest,
  NetworkFeed,
  ProfilesFeed,
  ReconciliationFeed,
  HotspotsFeed,
  ScaleFeed,
  VocabFeed,
  QuestionsFeed,
  PersonsFeed,
  GenderNoiseFeed,
  Canonical,
  Reports,
  RoutingFeed,
  RunLog,
} from './types'

/**
 * Everything the client reads, all of it produced by the engine.
 *
 * `corpus/` is synced from data/corpus by scripts/sync-corpus.mjs.
 * `data/` is written by scripts/export_web.py.
 * Both land in public/ and are copied verbatim into dist/, so development and
 * production resolve the same paths.
 *
 * Every path here is RELATIVE, with no leading slash, and that is deliberate.
 * An absolute '/data/eval.json' resolves against the domain root, so the
 * bundle breaks the moment it is served under a subpath. A relative path
 * resolves against the document, which under hash routing is always
 * index.html whatever route the user is on. Verified by
 * web/scripts/verify-dist.mjs, which fails the build on a leading slash.
 */
export const SOURCES = {
  manifest: 'corpus/manifest.json',
  corpus: 'corpus/corpus_stats.json',
  blocking: 'corpus/blocking_report.json',
  evaluation: 'data/eval.json',
  canonical: 'data/canonical.json',
  routing: 'data/routing.json',
  identities: 'data/identities.json',
  network: 'data/network.json',
  cases: 'data/cases.json',
  profiles: 'data/profiles.json',
  reconciliation: 'data/reconciliation.json',
  hotspots: 'data/hotspots.json',
  scale: 'data/scale.json',
  vocabulary: 'data/vocabulary.json',
  questions: 'data/questions.json',
  persons: 'data/persons.json',
  genderNoise: 'data/gender_noise.json',
  runlog: 'data/runlog.json',
} as const

export type LoadState =
  | { status: 'loading' }
  | { status: 'ready'; reports: Reports }
  | { status: 'error'; message: string }

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: 'no-store' })
  if (!response.ok) throw new Error(`${url} returned ${response.status}`)
  return (await response.json()) as T
}

async function optional<T>(url: string, guard: (value: T) => boolean): Promise<T | null> {
  try {
    const value = await getJson<T>(url)
    return guard(value) ? value : null
  } catch {
    return null
  }
}

/**
 * The corpus audit is required. Everything downstream is optional and its
 * screen says which command produces it, because an evaluator may well have
 * run `make gen` without `make eval`. Nothing is ever faked to fill a gap.
 */
export function useReports(): LoadState {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [manifest, corpus] = await Promise.all([
          getJson<Manifest>(SOURCES.manifest),
          getJson<CorpusStats>(SOURCES.corpus),
        ])
        if (!corpus?.recoverability || !manifest?.counts) {
          throw new Error('corpus report shape not recognised')
        }
        const [blocking, evaluation, routing, identities, network, cases, profiles, reconciliation, hotspots, scale, vocabulary, questions, persons, genderNoise, canonical, runlog] =
          await Promise.all([
            optional<BlockingReport>(SOURCES.blocking, (v) => Boolean(v?.ceiling)),
            optional<EvalReport>(SOURCES.evaluation, (v) => Boolean(v?.headline)),
            optional<RoutingFeed>(SOURCES.routing, (v) => Array.isArray(v?.pairs)),
            optional<IdentityFeed>(SOURCES.identities, (v) =>
              Array.isArray(v?.identities),
            ),
            optional<NetworkFeed>(SOURCES.network, (v) => Array.isArray(v?.nodes)),
            optional<CasesFeed>(SOURCES.cases, (v) => Array.isArray(v?.cases)),
            optional<ProfilesFeed>(SOURCES.profiles, (v) => Array.isArray(v?.profiles)),
            optional<ReconciliationFeed>(SOURCES.reconciliation, (v) => Boolean(v?.totals)),
            optional<HotspotsFeed>(SOURCES.hotspots, (v) => Array.isArray(v?.districts)),
            optional<ScaleFeed>(SOURCES.scale, (v) => Array.isArray(v?.runs)),
            optional<VocabFeed>(SOURCES.vocabulary, (v) => Array.isArray(v?.runs)),
            optional<QuestionsFeed>(SOURCES.questions, (v) => Array.isArray(v?.questions)),
            optional<PersonsFeed>(SOURCES.persons, (v) => Boolean(v?.combined)),
            optional<GenderNoiseFeed>(SOURCES.genderNoise, (v) => Array.isArray(v?.runs)),
            optional<Canonical>(SOURCES.canonical, (v) => Boolean(v?.headline)),
            optional<RunLog>(SOURCES.runlog, (v) => Boolean(v?.run_id)),
          ])
        if (cancelled) return
        setState({
          status: 'ready',
          reports: {
            manifest, corpus, blocking, evaluation, routing,
            identities, network, cases, profiles, reconciliation, hotspots, scale,
            vocabulary, questions, persons, genderNoise, canonical, runlog,
          },
        })
      } catch (error) {
        if (!cancelled) {
          setState({
            status: 'error',
            message: error instanceof Error ? error.message : String(error),
          })
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  return state
}

/* ------------------------------------------------------------- formatting */

export const n = (value: number) => value.toLocaleString('en-IN')

export const pct = (value: number, places = 2) => `${value.toFixed(places)}%`

/** Ratios in the reports are fractions. Percent formatting lives here so no
 *  screen has to remember which is which. */
export const asPct = (fraction: number, places = 2) =>
  `${(fraction * 100).toFixed(places)}%`

export function timestamp(iso?: string): string {
  if (!iso) return 'unknown'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toISOString().replace('T', ' ').replace(/\.\d+Z$/, 'Z').replace('Z', ' UTC')
}
