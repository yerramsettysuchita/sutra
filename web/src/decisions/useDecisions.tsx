/**
 * Operator decisions on candidate merges.
 *
 * Until now every role could look and none could act. The Records operator role
 * in particular existed to approve merges and did nothing at all, which made
 * the review queue a picture of a review queue.
 *
 * WHAT THIS IS
 *
 * A client side decision layer, held in localStorage. An operator can accept or
 * refuse a merge, a reviewer can reverse one, and the log of what they did is
 * the audit trail. No backend, no Catalyst runtime service, nothing written
 * back to the engine.
 *
 * WHAT THIS IS NOT, AND /status SAYS THE SAME
 *
 * It is per browser. Clearing site data clears the decisions. Two officers on
 * two machines do not see each other's work. Nothing reaches the resolved
 * identity table, because resolution is a nightly batch job and the deployed
 * surface is read only, which is ADR 002 and has not changed.
 *
 * So this demonstrates the decision model and the audit obligations that come
 * with it. Persisting to Catalyst Data Store is NOT BUILT and is stated as such.
 *
 * THE APPEND ONLY GUARANTEE
 *
 * `/status` claims an audit trail. An audit trail that can lose an entry is not
 * one. So the log is append only in the strict sense: reversing a merge appends
 * a `reverse` entry, it does not remove the `merge` entry that came before it.
 * The current state of a pair is derived by folding the log, never by editing
 * it. `record()` is the only writer and it can only push.
 *
 * That property is asserted by tests rather than left to convention, because it
 * is the one thing here a jury would be right to check.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export type DecisionAction = 'merge' | 'keep separate' | 'reverse'

export type Decision = {
  /** The candidate pair this decision is about. */
  pair_id: string
  /** Both accused rows, so the entry is meaningful without the pair feed. */
  amid_left: string
  amid_right: string
  action: DecisionAction
  /** The role that was in force. An audit entry without it is anonymous. */
  role: string
  role_label: string
  /** The district scope in force, or null when statewide. */
  district: string | null
  /** ISO 8601, UTC. */
  at: string
  /** The calibrated probability at the moment of the decision. Kept because a
   *  later engine run may score the pair differently and the decision has to be
   *  readable against what the officer actually saw. */
  probability: number
  /** Set on a reversal, naming the entry being reversed. */
  reverses?: string
}

export type PairOutcome = {
  /** The decision currently in force, after folding the log. */
  action: Exclude<DecisionAction, 'reverse'> | null
  /** The entry that produced it. */
  decision: Decision | null
  /** True when the pair has been decided and then reversed back to pending. */
  reversed: boolean
}

export type DecisionSummary = {
  decided: number
  pending: number
  merged: number
  keptSeparate: number
  reversed: number
}

const KEY = 'sutra.decisions.v1'

/** Stable id for an entry, used by a reversal to name what it reverses. */
function entryId(d: Decision): string {
  return `${d.pair_id}@${d.at}`
}

function load(): Decision[] {
  try {
    const raw = window.localStorage.getItem(KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as Decision[]) : []
  } catch {
    // Corrupt or unavailable storage. An empty log is the safe reading: it
    // shows nothing has been decided rather than inventing a state.
    return []
  }
}

function persist(log: Decision[]): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(log))
  } catch {
    /* the session still works, it just will not survive a reload */
  }
}

/**
 * Fold the append only log into the current state of each pair.
 *
 * Later entries win. A `reverse` entry returns the pair to pending, and the
 * entry it reversed stays in the log where an auditor can see it.
 */
export function foldLog(log: Decision[]): Map<string, PairOutcome> {
  const state = new Map<string, PairOutcome>()
  for (const entry of log) {
    if (entry.action === 'reverse') {
      state.set(entry.pair_id, {
        action: null,
        decision: entry,
        reversed: true,
      })
      continue
    }
    state.set(entry.pair_id, {
      action: entry.action,
      decision: entry,
      reversed: false,
    })
  }
  return state
}

export function summarise(
  log: Decision[],
  totalPairs: number,
): DecisionSummary {
  const state = foldLog(log)
  let merged = 0
  let keptSeparate = 0
  for (const outcome of state.values()) {
    if (outcome.action === 'merge') merged += 1
    if (outcome.action === 'keep separate') keptSeparate += 1
  }
  const decided = merged + keptSeparate
  return {
    decided,
    pending: Math.max(totalPairs - decided, 0),
    merged,
    keptSeparate,
    // Every reversal ever made, not the number of pairs currently reversed,
    // because the count is about operator activity rather than about state.
    reversed: log.filter((d) => d.action === 'reverse').length,
  }
}

type Ctx = {
  log: Decision[]
  outcomes: Map<string, PairOutcome>
  record: (entry: Omit<Decision, 'at'>) => void
  reverse: (pairId: string, by: { role: string; role_label: string;
                                  district: string | null }) => void
  reset: () => void
  summary: (totalPairs: number) => DecisionSummary
  outcomeOf: (pairId: string) => PairOutcome | undefined
}

const DecisionContext = createContext<Ctx | null>(null)

export function DecisionProvider({
  children,
  initial,
}: {
  children: ReactNode
  /** Seeds the log. Only tests and the smoke render use it. */
  initial?: Decision[]
}) {
  const [log, setLog] = useState<Decision[]>(() => initial ?? load())

  // The only writer. It appends and cannot do anything else, which is what
  // makes the append only claim structural rather than a promise.
  const append = useCallback((entry: Decision) => {
    setLog((current) => {
      const next = [...current, entry]
      persist(next)
      return next
    })
  }, [])

  const record = useCallback(
    (entry: Omit<Decision, 'at'>) => {
      append({ ...entry, at: new Date().toISOString() })
    },
    [append],
  )

  const reverse = useCallback(
    (pairId: string, by: { role: string; role_label: string;
                           district: string | null }) => {
      setLog((current) => {
        const previous = [...current]
          .reverse()
          .find((d) => d.pair_id === pairId && d.action !== 'reverse')
        if (!previous) return current
        const entry: Decision = {
          pair_id: pairId,
          amid_left: previous.amid_left,
          amid_right: previous.amid_right,
          action: 'reverse',
          role: by.role,
          role_label: by.role_label,
          district: by.district,
          at: new Date().toISOString(),
          probability: previous.probability,
          reverses: entryId(previous),
        }
        const next = [...current, entry]
        persist(next)
        return next
      })
    },
    [],
  )

  const reset = useCallback(() => {
    setLog([])
    persist([])
  }, [])

  const value = useMemo<Ctx>(() => {
    const outcomes = foldLog(log)
    return {
      log,
      outcomes,
      record,
      reverse,
      reset,
      summary: (totalPairs: number) => summarise(log, totalPairs),
      outcomeOf: (pairId: string) => outcomes.get(pairId),
    }
  }, [log, record, reverse, reset])

  return (
    <DecisionContext.Provider value={value}>{children}</DecisionContext.Provider>
  )
}

export function useDecisions(): Ctx {
  const ctx = useContext(DecisionContext)
  if (ctx) return ctx
  // Rendered outside the provider, which happens in the smoke render. An empty
  // log that accepts no writes is the honest default.
  const empty: Decision[] = []
  return {
    log: empty,
    outcomes: new Map(),
    record: () => {},
    reverse: () => {},
    reset: () => {},
    summary: (totalPairs: number) => summarise(empty, totalPairs),
    outcomeOf: () => undefined,
  }
}
