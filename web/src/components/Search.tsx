/**
 * Find a person, or a crime number.
 *
 * Every screen in this application was browse only. An investigating officer
 * does not browse. They arrive holding a name somebody gave them at a counter,
 * or a crime number off a piece of paper, and the first thing they need is the
 * record behind it.
 *
 * WHAT IT MATCHES
 *
 * Any recorded rendering of a name, in either script. That is the whole point:
 * the identity carries every variant the record ever used, so typing the Latin
 * spelling finds the row written in Kannada and the other way round. A search
 * that only matched the string as typed would be the naive join this project
 * exists to argue against.
 *
 * Also crime numbers, because that is the other thing an officer holds.
 *
 * SCOPE
 *
 * It searches what the active role can see. An officer scoped to one district
 * gets hits from that district, because the scope filter has already removed
 * everything else from the reports this reads. Nothing here re-derives access,
 * which means search cannot leak past the filter by accident.
 */

import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useT } from '../i18n/useLanguage'
import { useScope } from '../scope/useScope'
import type { Reports } from '../data/types'

type Hit = {
  identity: string
  label: string
  detail: string
  /** What matched, so the officer can see why this row came back. */
  matched: string
  kind: 'name' | 'crime number'
}

const MAX_HITS = 8

function normalise(text: string): string {
  return text.trim().toLowerCase()
}

export function Search({ reports }: { reports: Reports }) {
  const t = useT()
  const scope = useScope()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const hits = useMemo<Hit[]>(() => {
    const q = normalise(query)
    if (q.length < 2) return []
    const found: Hit[] = []
    const seen = new Set<string>()

    for (const identity of reports.identities?.identities ?? []) {
      if (found.length >= MAX_HITS) break

      // Every rendering the record ever used, in every script.
      const variant = identity.variants.find((v) =>
        normalise(v.name).includes(q),
      )
      if (variant && !seen.has(identity.identity)) {
        seen.add(identity.identity)
        found.push({
          identity: identity.identity,
          label: variant.name,
          detail: `${identity.record_count} records, ${identity.case_count} cases, ${identity.distinct_renderings} renderings`,
          matched: variant.name,
          kind: 'name',
        })
        continue
      }

      const crime = identity.cases.find(
        (c) => normalise(c.crime_no).includes(q),
      )
      if (crime && !seen.has(identity.identity)) {
        seen.add(identity.identity)
        found.push({
          identity: identity.identity,
          label: crime.name,
          detail: `${crime.crime_no}, ${crime.station}, ${crime.district}`,
          matched: crime.crime_no,
          kind: 'crime number',
        })
      }
    }
    return found
  }, [query, reports])

  // The operator cannot open the profile screen, so offering a jump to it
  // would be a control that fails. Roles that cannot reach /network do not get
  // the field.
  if (!scope.allows('/network')) return null

  const go = (identity: string) => {
    setOpen(false)
    setQuery('')
    navigate(`/network?identity=${encodeURIComponent(identity)}`)
  }

  return (
    <div className="search" role="search">
      <label className="search__label" htmlFor="sutra-search">
        {t('Find')}
      </label>
      <input
        id="sutra-search"
        ref={inputRef}
        className="search__input"
        type="search"
        autoComplete="off"
        placeholder={t('Name in either script, or a crime number')}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setOpen(false)
            setQuery('')
          }
          if (e.key === 'Enter' && hits[0]) go(hits[0].identity)
        }}
        aria-expanded={open && query.length >= 2}
        aria-controls="sutra-search-results"
        aria-describedby="sutra-search-help"
      />
      <span className="visually-hidden" id="sutra-search-help">
        Matches any recorded rendering of a name in Latin or Kannada script, or
        a crime number, within the jurisdiction your role can see.
      </span>

      {open && query.length >= 2 && (
        <div
          className="search__results"
          id="sutra-search-results"
          role="listbox"
          aria-label="Search results"
        >
          {hits.length === 0 ? (
            <p className="search__empty">
              Nothing matches <strong>{query}</strong> in{' '}
              {scope.district ?? 'the state'}. The identity export carries the
              first {reports.identities?.shown ?? 0} identities, so a person
              outside that set will not appear.
            </p>
          ) : (
            <ul>
              {hits.map((hit) => (
                <li key={hit.identity}>
                  <button
                    type="button"
                    className="search__hit"
                    role="option"
                    aria-selected="false"
                    onClick={() => go(hit.identity)}
                  >
                    <span className="search__hit-name">{hit.label}</span>
                    <span className="search__hit-id mono">{hit.identity}</span>
                    <span className="search__hit-detail">
                      {hit.detail}
                      <em> matched on {hit.kind}</em>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
