/**
 * Query console.
 *
 * This is a structured query interface, not a chat box. No language model runs
 * anywhere in this application, and the screen says so at the top rather than
 * implying otherwise through a text input and a send button.
 *
 * Fifteen parameterised questions the officer selects and fills in. Each answer
 * shows the equivalent SQL against the KSP schema, the row count, and the file
 * the answer actually came from. The SQL is what the query would be if it ran
 * against the database. The result is computed here over the exported feeds,
 * and the two are labelled distinctly so nobody mistakes one for the other.
 */

import { useMemo, useState, type ReactNode } from 'react'

import {
  Bar,
  DataTable,
  Metric,
  MetricRow,
  Panel,
  Rule,
  StatusPill,
  type Column,
} from '../components/primitives'
import { NotBuilt } from '../components/NotBuilt'
import { HeroFigure, MethodBars } from '../components/hero'
import { n } from '../data/useReports'
import type { Profile, Reports } from '../data/types'

type Row = Record<string, string | number>

type Answer = {
  rows: Row[]
  columns: Column<Row>[]
  sql: string
  source: string
  note?: ReactNode
}

type Param = {
  key: string
  label: string
  kind: 'select' | 'number'
  options?: string[]
  min?: number
  max?: number
}

type Question = {
  id: string
  text: string
  params: Param[]
  run: (values: Record<string, string>, reports: Reports) => Answer
}

const textColumn = (key: string, header: string, code = false): Column<Row> => ({
  key,
  header,
  code,
  render: (r) => String(r[key] ?? ''),
})

const numColumn = (key: string, header: string): Column<Row> => ({
  key,
  header,
  numeric: true,
  render: (r) => String(r[key] ?? ''),
})

function profilesOf(reports: Reports): Profile[] {
  return reports.profiles?.profiles ?? []
}

function districtOptions(reports: Reports): string[] {
  const set = new Set<string>()
  profilesOf(reports).forEach((p) => p.districts.forEach((d) => set.add(d.district)))
  return [...set].sort()
}

function stationOptions(reports: Reports): string[] {
  const set = new Set<string>()
  profilesOf(reports).forEach((p) => p.stations.forEach((s) => set.add(s.station)))
  return [...set].sort()
}

function identityOptions(reports: Reports): string[] {
  return profilesOf(reports)
    .filter((p) => p.co_accused_count > 0 || p.cases > 1)
    .slice(0, 120)
    .map((p) => p.identity)
}

function offenceOptions(reports: Reports): string[] {
  const set = new Set<string>()
  profilesOf(reports).forEach((p) => p.mo_signature.forEach((m) => set.add(m.offence)))
  reports.cases?.cases.forEach((c) => set.add(c.subhead))
  return [...set].sort()
}

const PROFILES_SOURCE = '/data/profiles.json, built by engine/downstream/profiles.py'
const CASES_SOURCE = '/data/cases.json, built by engine/downstream/undetected.py'
const IDENTITIES_SOURCE = '/data/identities.json, from data/corpus/resolved_identities.csv'

const QUESTIONS: Question[] = [
  {
    id: 'two-districts',
    text: 'Which identities appear in both <A> and <B>',
    params: [
      { key: 'a', label: 'District A', kind: 'select' },
      { key: 'b', label: 'District B', kind: 'select' },
    ],
    run: (v, reports) => {
      const rows = profilesOf(reports)
        .filter(
          (p) =>
            p.districts.some((d) => d.district === v.a) &&
            p.districts.some((d) => d.district === v.b),
        )
        .map((p) => ({
          identity: p.identity,
          on_record_as: p.label,
          cases: p.cases,
          districts: p.districts_touched,
          renderings: p.distinct_renderings,
        }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Identity', true),
          textColumn('on_record_as', 'On record as'),
          numColumn('cases', 'Cases'),
          numColumn('districts', 'Districts'),
          numColumn('renderings', 'Renderings'),
        ],
        sql: `SELECT ri.ResolvedIdentityID, COUNT(DISTINCT cm.CaseMasterID) AS cases
FROM ResolvedIdentity ri
JOIN Accused a  ON a.AccusedMasterID = ri.AccusedMasterID
JOIN CaseMaster cm ON cm.CaseMasterID = a.CaseMasterID
JOIN District d ON d.DistrictID = cm.DistrictID
WHERE d.DistrictName IN ('${v.a}', '${v.b}')
GROUP BY ri.ResolvedIdentityID
HAVING COUNT(DISTINCT d.DistrictName) = 2;`,
        source: PROFILES_SOURCE,
        note: (
          <>
            This question is unanswerable on the KSP schema as supplied.
            <span className="mono"> ResolvedIdentity</span> is the table SUTRA
            adds. Without it the join has no person key and the same offender in
            two districts is two unrelated rows.
          </>
        ),
      }
    },
  },
  {
    id: 'repeat-at-station',
    text: 'Repeat offenders at <station> with more than <N> cases',
    params: [
      { key: 'station', label: 'Station', kind: 'select' },
      { key: 'min', label: 'Minimum cases', kind: 'number', min: 2, max: 16 },
    ],
    run: (v, reports) => {
      const min = Number(v.min || 2)
      const rows = profilesOf(reports)
        .filter(
          (p) => p.stations.some((s) => s.station === v.station) && p.cases > min,
        )
        .map((p) => ({
          identity: p.identity,
          on_record_as: p.label,
          cases: p.cases,
          at_this_station:
            p.stations.find((s) => s.station === v.station)?.cases ?? 0,
          first: p.first_case ?? '',
          last: p.last_case ?? '',
        }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Identity', true),
          textColumn('on_record_as', 'On record as'),
          numColumn('cases', 'Total cases'),
          numColumn('at_this_station', 'At this station'),
          textColumn('first', 'First', true),
          textColumn('last', 'Last', true),
        ],
        sql: `SELECT ri.ResolvedIdentityID, COUNT(DISTINCT cm.CaseMasterID) AS cases
FROM ResolvedIdentity ri
JOIN Accused a  ON a.AccusedMasterID = ri.AccusedMasterID
JOIN CaseMaster cm ON cm.CaseMasterID = a.CaseMasterID
JOIN Unit u ON u.UnitID = cm.UnitID
WHERE u.UnitName = '${v.station}'
GROUP BY ri.ResolvedIdentityID
HAVING COUNT(DISTINCT cm.CaseMasterID) > ${min};`,
        source: PROFILES_SOURCE,
      }
    },
  },
  {
    id: 'co-accused',
    text: 'Who has <identity> been co accused with',
    params: [{ key: 'identity', label: 'Identity', kind: 'select' }],
    run: (v, reports) => {
      const profile = profilesOf(reports).find((p) => p.identity === v.identity)
      const rows = (profile?.co_accused_circle ?? []).map((c) => ({
        identity: c.identity,
        on_record_as: c.label,
        shared_cases: c.shared_cases,
        visibility: c.recovered ? 'recovered by resolution' : 'visible before',
      }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Co accused', true),
          textColumn('on_record_as', 'On record as'),
          numColumn('shared_cases', 'Shared cases'),
          textColumn('visibility', 'Visibility'),
        ],
        sql: `SELECT other.ResolvedIdentityID, COUNT(DISTINCT cm.CaseMasterID) AS shared
FROM ResolvedIdentity self
JOIN Accused sa ON sa.AccusedMasterID = self.AccusedMasterID
JOIN CaseMaster cm ON cm.CaseMasterID = sa.CaseMasterID
JOIN Accused oa ON oa.CaseMasterID = cm.CaseMasterID
JOIN ResolvedIdentity other ON other.AccusedMasterID = oa.AccusedMasterID
WHERE self.ResolvedIdentityID = '${v.identity}'
  AND other.ResolvedIdentityID <> self.ResolvedIdentityID
GROUP BY other.ResolvedIdentityID
ORDER BY shared DESC;`,
        source: PROFILES_SOURCE,
        note: (
          <>
            Rows marked recovered were invisible before resolution, because the
            link attaches through a name rendering a naive join would have read
            as a different person.
          </>
        ),
      }
    },
  },
  {
    id: 'undetected-for-identity',
    text: 'Undetected cases matching <identity>',
    params: [{ key: 'identity', label: 'Identity', kind: 'select' }],
    run: (v, reports) => {
      const rows: Row[] = []
      reports.cases?.cases.forEach((entry) => {
        const hit = entry.candidates.find((c) => c.identity === v.identity)
        if (hit) {
          rows.push({
            crime_no: entry.crime_no,
            offence: entry.subhead,
            station: entry.station,
            registered: entry.registered,
            rank: hit.rank,
            score: hit.score.toFixed(4),
            nearest_km: hit.signals.nearest_km.toFixed(1),
          })
        }
      })
      rows.sort((a, b) => Number(a.rank) - Number(b.rank))
      return {
        rows,
        columns: [
          textColumn('crime_no', 'Crime number', true),
          textColumn('offence', 'Offence'),
          textColumn('station', 'Station'),
          textColumn('registered', 'Registered', true),
          numColumn('rank', 'Rank'),
          numColumn('score', 'Score'),
          numColumn('nearest_km', 'Nearest km'),
        ],
        sql: `-- Layer 8 ranking, not a stored table. The equivalent retrieval is
SELECT cm.CrimeNo, cs.cstype
FROM CaseMaster cm
JOIN ChargesheetDetails cs ON cs.CaseMasterID = cm.CaseMasterID
WHERE cs.cstype = 'C'
-- then ranked by MO cosine over cm.BriefFacts, Haversine over cm.Latitude
-- and cm.Longitude, and the identity's active window.`,
        source: CASES_SOURCE,
        note: (
          <>
            An investigative lead requiring independent corroboration, not a
            prediction and not evidence.
          </>
        ),
      }
    },
  },
  {
    id: 'most-renderings',
    text: 'Identities written more than <N> different ways',
    params: [{ key: 'min', label: 'Minimum renderings', kind: 'number', min: 2, max: 15 }],
    run: (v, reports) => {
      const min = Number(v.min || 3)
      const rows = profilesOf(reports)
        .filter((p) => p.distinct_renderings > min)
        .map((p) => ({
          identity: p.identity,
          renderings: p.distinct_renderings,
          records: p.records,
          cases: p.cases,
          all: p.renderings.map((r) => r.name).join(' / '),
        }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Identity', true),
          numColumn('renderings', 'Renderings'),
          numColumn('records', 'Records'),
          numColumn('cases', 'Cases'),
          textColumn('all', 'Written as'),
        ],
        sql: `SELECT ri.ResolvedIdentityID, COUNT(DISTINCT a.AccusedName) AS renderings
FROM ResolvedIdentity ri
JOIN Accused a ON a.AccusedMasterID = ri.AccusedMasterID
GROUP BY ri.ResolvedIdentityID
HAVING COUNT(DISTINCT a.AccusedName) > ${min};`,
        source: PROFILES_SOURCE,
        note: <>Each distinct rendering is a person a naive join would invent.</>,
      }
    },
  },
  {
    id: 'offence-signature',
    text: 'Identities whose record is mostly <offence>',
    params: [{ key: 'offence', label: 'Offence', kind: 'select' }],
    run: (v, reports) => {
      const rows = profilesOf(reports)
        .map((p) => ({
          p,
          entry: p.mo_signature.find((m) => m.offence === v.offence),
        }))
        .filter((x) => x.entry && x.entry.share >= 0.5 && x.p.cases > 1)
        .map(({ p, entry }) => ({
          identity: p.identity,
          on_record_as: p.label,
          cases: p.cases,
          of_this_offence: entry!.cases,
          share: entry!.share.toFixed(2),
          circle: p.primary_circle ?? '',
        }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Identity', true),
          textColumn('on_record_as', 'On record as'),
          numColumn('cases', 'Cases'),
          numColumn('of_this_offence', 'Of this offence'),
          numColumn('share', 'Share'),
          textColumn('circle', 'Circle', true),
        ],
        sql: `SELECT ri.ResolvedIdentityID,
       SUM(CASE WHEN csh.CrimeSubHeadName = '${v.offence}' THEN 1 ELSE 0 END) * 1.0
         / COUNT(*) AS share
FROM ResolvedIdentity ri
JOIN Accused a ON a.AccusedMasterID = ri.AccusedMasterID
JOIN CaseMaster cm ON cm.CaseMasterID = a.CaseMasterID
JOIN CrimeSubHead csh ON csh.CrimeSubHeadID = cm.CrimeSubHeadID
GROUP BY ri.ResolvedIdentityID
HAVING share >= 0.5;`,
        source: PROFILES_SOURCE,
      }
    },
  },
  {
    id: 'travelling',
    text: 'Identities active in more than <N> districts',
    params: [{ key: 'min', label: 'Minimum districts', kind: 'number', min: 1, max: 6 }],
    run: (v, reports) => {
      const min = Number(v.min || 1)
      const rows = profilesOf(reports)
        .filter((p) => p.districts_touched > min)
        .map((p) => ({
          identity: p.identity,
          on_record_as: p.label,
          districts: p.districts_touched,
          where: p.districts.map((d) => `${d.district} (${d.cases})`).join(', '),
          cases: p.cases,
        }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Identity', true),
          textColumn('on_record_as', 'On record as'),
          numColumn('districts', 'Districts'),
          numColumn('cases', 'Cases'),
          textColumn('where', 'Where'),
        ],
        sql: `SELECT ri.ResolvedIdentityID, COUNT(DISTINCT cm.DistrictID) AS districts
FROM ResolvedIdentity ri
JOIN Accused a ON a.AccusedMasterID = ri.AccusedMasterID
JOIN CaseMaster cm ON cm.CaseMasterID = a.CaseMasterID
GROUP BY ri.ResolvedIdentityID
HAVING COUNT(DISTINCT cm.DistrictID) > ${min};`,
        source: PROFILES_SOURCE,
        note: <>The offenders a station level system loses entirely.</>,
      }
    },
  },
  {
    id: 'recovered-links',
    text: 'Identities with more than <N> co offender links recovered by resolution',
    params: [{ key: 'min', label: 'Minimum recovered', kind: 'number', min: 1, max: 10 }],
    run: (v, reports) => {
      const min = Number(v.min || 1)
      const rows = profilesOf(reports)
        .filter((p) => p.recovered_relationships > min)
        .map((p) => ({
          identity: p.identity,
          on_record_as: p.label,
          recovered: p.recovered_relationships,
          total_links: p.co_accused_count,
          cases: p.cases,
        }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Identity', true),
          textColumn('on_record_as', 'On record as'),
          numColumn('recovered', 'Recovered links'),
          numColumn('total_links', 'Total links'),
          numColumn('cases', 'Cases'),
        ],
        sql: `-- Recovery is a property of the resolution, not a column.
-- An edge is recovered when it attaches through a rendering other than the
-- identity's most frequent one, so a GROUP BY AccusedName would have hung it
-- off a different node.`,
        source: PROFILES_SOURCE,
      }
    },
  },
  {
    id: 'active-window',
    text: 'Identities active for more than <N> days',
    params: [{ key: 'min', label: 'Minimum days', kind: 'number', min: 30, max: 1800 }],
    run: (v, reports) => {
      const min = Number(v.min || 365)
      const rows = profilesOf(reports)
        .filter((p) => p.active_days > min)
        .map((p) => ({
          identity: p.identity,
          on_record_as: p.label,
          days: p.active_days,
          first: p.first_case ?? '',
          last: p.last_case ?? '',
          cases: p.cases,
        }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Identity', true),
          textColumn('on_record_as', 'On record as'),
          numColumn('days', 'Active days'),
          textColumn('first', 'First', true),
          textColumn('last', 'Last', true),
          numColumn('cases', 'Cases'),
        ],
        sql: `SELECT ri.ResolvedIdentityID,
       JULIANDAY(MAX(cm.CrimeRegisteredDate)) - JULIANDAY(MIN(cm.CrimeRegisteredDate))
         AS active_days
FROM ResolvedIdentity ri
JOIN Accused a ON a.AccusedMasterID = ri.AccusedMasterID
JOIN CaseMaster cm ON cm.CaseMasterID = a.CaseMasterID
GROUP BY ri.ResolvedIdentityID
HAVING active_days > ${min};`,
        source: PROFILES_SOURCE,
      }
    },
  },
  {
    id: 'undetected-at-station',
    text: 'Undetected cases at <station>',
    params: [{ key: 'station', label: 'Station', kind: 'select' }],
    run: (v, reports) => {
      const rows = (reports.cases?.cases ?? [])
        .filter((c) => c.station === v.station)
        .map((c) => ({
          crime_no: c.crime_no,
          offence: c.subhead,
          registered: c.registered,
          top_candidate: c.candidates[0]?.identity ?? '',
          top_score: c.candidates[0]?.score.toFixed(4) ?? '',
        }))
      return {
        rows,
        columns: [
          textColumn('crime_no', 'Crime number', true),
          textColumn('offence', 'Offence'),
          textColumn('registered', 'Registered', true),
          textColumn('top_candidate', 'Top candidate', true),
          numColumn('top_score', 'Score'),
        ],
        sql: `SELECT cm.CrimeNo, csh.CrimeSubHeadName, cm.CrimeRegisteredDate
FROM CaseMaster cm
JOIN ChargesheetDetails cs ON cs.CaseMasterID = cm.CaseMasterID
JOIN Unit u ON u.UnitID = cm.UnitID
JOIN CrimeSubHead csh ON csh.CrimeSubHeadID = cm.CrimeSubHeadID
WHERE cs.cstype = 'C' AND u.UnitName = '${v.station}';`,
        source: CASES_SOURCE,
      }
    },
  },
  {
    id: 'cross-script',
    text: 'Identities recorded in more than one script',
    params: [],
    run: (_v, reports) => {
      const rows = (reports.identities?.identities ?? [])
        .filter((i) => i.scripts.length > 1)
        .map((i) => ({
          identity: i.identity,
          scripts: i.scripts.join(' and '),
          renderings: i.distinct_renderings,
          cases: i.case_count,
          all: i.variants.map((v) => v.name).join(' / '),
        }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Identity', true),
          textColumn('scripts', 'Scripts'),
          numColumn('renderings', 'Renderings'),
          numColumn('cases', 'Cases'),
          textColumn('all', 'Written as'),
        ],
        sql: `-- Script is not a column. It is derived from the Unicode block of
-- Accused.AccusedName, which is why Layer 1 folding exists.
SELECT ri.ResolvedIdentityID, a.AccusedName
FROM ResolvedIdentity ri
JOIN Accused a ON a.AccusedMasterID = ri.AccusedMasterID;`,
        source: IDENTITIES_SOURCE,
        note: (
          <>
            The clearest demonstration of the finding. One person, two writing
            systems, nothing in the schema connecting them.
          </>
        ),
      }
    },
  },
  {
    id: 'largest-merges',
    text: 'The largest merges, identities built from more than <N> records',
    params: [{ key: 'min', label: 'Minimum records', kind: 'number', min: 2, max: 16 }],
    run: (v, reports) => {
      const min = Number(v.min || 5)
      const rows = profilesOf(reports)
        .filter((p) => p.records > min)
        .map((p) => ({
          identity: p.identity,
          records: p.records,
          cases: p.cases,
          before: p.before_resolution.apparent_people,
          largest_fragment: p.before_resolution.largest_fragment_cases,
        }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Identity', true),
          numColumn('records', 'Records merged'),
          numColumn('cases', 'Cases'),
          numColumn('before', 'Apparent people before'),
          numColumn('largest_fragment', 'Largest fragment'),
        ],
        sql: `SELECT ri.ResolvedIdentityID, COUNT(*) AS records
FROM ResolvedIdentity ri
GROUP BY ri.ResolvedIdentityID
HAVING COUNT(*) > ${min};`,
        source: PROFILES_SOURCE,
        note: (
          <>
            The largest fragment column is what a naive join would have seen as
            this person's entire history.
          </>
        ),
      }
    },
  },
  {
    id: 'station-load',
    text: 'Which identities are most active at <station>',
    params: [{ key: 'station', label: 'Station', kind: 'select' }],
    run: (v, reports) => {
      const rows = profilesOf(reports)
        .map((p) => ({ p, s: p.stations.find((s) => s.station === v.station) }))
        .filter((x) => x.s)
        .sort((a, b) => (b.s!.cases ?? 0) - (a.s!.cases ?? 0))
        .map(({ p, s }) => ({
          identity: p.identity,
          on_record_as: p.label,
          here: s!.cases,
          total: p.cases,
          offence: p.mo_signature[0]?.offence ?? '',
        }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Identity', true),
          textColumn('on_record_as', 'On record as'),
          numColumn('here', 'Cases here'),
          numColumn('total', 'Cases total'),
          textColumn('offence', 'Most common offence'),
        ],
        sql: `SELECT ri.ResolvedIdentityID, COUNT(DISTINCT cm.CaseMasterID) AS here
FROM ResolvedIdentity ri
JOIN Accused a ON a.AccusedMasterID = ri.AccusedMasterID
JOIN CaseMaster cm ON cm.CaseMasterID = a.CaseMasterID
JOIN Unit u ON u.UnitID = cm.UnitID
WHERE u.UnitName = '${v.station}'
GROUP BY ri.ResolvedIdentityID
ORDER BY here DESC;`,
        source: PROFILES_SOURCE,
      }
    },
  },
  {
    id: 'undetected-by-offence',
    text: 'Undetected <offence> cases and their top candidate',
    params: [{ key: 'offence', label: 'Offence', kind: 'select' }],
    run: (v, reports) => {
      const rows = (reports.cases?.cases ?? [])
        .filter((c) => c.subhead === v.offence)
        .map((c) => ({
          crime_no: c.crime_no,
          station: c.station,
          district: c.district,
          registered: c.registered,
          top_candidate: c.candidates[0]?.identity ?? '',
          score: c.candidates[0]?.score.toFixed(4) ?? '',
        }))
      return {
        rows,
        columns: [
          textColumn('crime_no', 'Crime number', true),
          textColumn('station', 'Station'),
          textColumn('district', 'District'),
          textColumn('registered', 'Registered', true),
          textColumn('top_candidate', 'Top candidate', true),
          numColumn('score', 'Score'),
        ],
        sql: `SELECT cm.CrimeNo, u.UnitName, d.DistrictName, cm.CrimeRegisteredDate
FROM CaseMaster cm
JOIN ChargesheetDetails cs ON cs.CaseMasterID = cm.CaseMasterID
JOIN CrimeSubHead csh ON csh.CrimeSubHeadID = cm.CrimeSubHeadID
JOIN Unit u ON u.UnitID = cm.UnitID
JOIN District d ON d.DistrictID = cm.DistrictID
WHERE cs.cstype = 'C' AND csh.CrimeSubHeadName = '${v.offence}';`,
        source: CASES_SOURCE,
      }
    },
  },
  {
    id: 'solo',
    text: 'Repeat offenders with no known co accused',
    params: [],
    run: (_v, reports) => {
      const rows = profilesOf(reports)
        .filter((p) => p.co_accused_count === 0 && p.cases > 1)
        .map((p) => ({
          identity: p.identity,
          on_record_as: p.label,
          cases: p.cases,
          offence: p.mo_signature[0]?.offence ?? '',
          circle: p.primary_circle ?? '',
        }))
      return {
        rows,
        columns: [
          textColumn('identity', 'Identity', true),
          textColumn('on_record_as', 'On record as'),
          numColumn('cases', 'Cases'),
          textColumn('offence', 'Most common offence'),
          textColumn('circle', 'Circle', true),
        ],
        sql: `SELECT ri.ResolvedIdentityID
FROM ResolvedIdentity ri
JOIN Accused a ON a.AccusedMasterID = ri.AccusedMasterID
GROUP BY ri.ResolvedIdentityID
HAVING COUNT(DISTINCT a.CaseMasterID) > 1
   AND NOT EXISTS (
     SELECT 1 FROM Accused other
     WHERE other.CaseMasterID = a.CaseMasterID
       AND other.AccusedMasterID <> a.AccusedMasterID);`,
        source: PROFILES_SOURCE,
      }
    },
  },
]

export function Ask({ reports }: { reports: Reports }) {
  const [questionId, setQuestionId] = useState(QUESTIONS[0]!.id)
  const [values, setValues] = useState<Record<string, string>>({})

  const options = useMemo(
    () => ({
      districts: districtOptions(reports),
      stations: stationOptions(reports),
      identities: identityOptions(reports),
      offences: offenceOptions(reports),
    }),
    [reports],
  )

  const question = QUESTIONS.find((q) => q.id === questionId) ?? QUESTIONS[0]!

  const optionsFor = (param: Param): string[] => {
    if (param.key === 'a' || param.key === 'b') return options.districts
    if (param.key === 'station') return options.stations
    if (param.key === 'identity') return options.identities
    if (param.key === 'offence') return options.offences
    return []
  }

  const filled: Record<string, string> = {}
  question.params.forEach((param) => {
    const chosen = values[`${question.id}:${param.key}`]
    if (chosen) {
      filled[param.key] = chosen
    } else if (param.kind === 'select') {
      const list = optionsFor(param)
      filled[param.key] = param.key === 'b' ? (list[1] ?? list[0] ?? '') : (list[0] ?? '')
    } else {
      filled[param.key] = String(param.min ?? 1)
    }
  })

  const ready = reports.profiles || reports.cases
  const answer = ready ? question.run(filled, reports) : null

  if (!ready) {
    return (
      <NotBuilt
        title="Query console"
        what="Structured questions over the resolved network, each showing the equivalent SQL."
        why="The Layer 8 export has not been produced, so there is nothing to query."
        command={'make resolve\nmake downstream\nmake export'}
      />
    )
  }

  return (
    <>
      <Panel
        id="console-honesty"
        title="Structured query console"
        eyebrow="signal"
        aside={<StatusPill label="no language model" tone="official" />}
      >
        <p className="note">
          <strong>This is a structured query interface, not a chat box.</strong>{' '}
          No language model runs in this application. You pick a question and
          fill in its parameters, and the console shows the equivalent SQL, the
          row count and the file the answer came from.
        </p>
        <p className="note">
          Natural language question answering and Kannada speech input are{' '}
          <strong>not built</strong>. The 150 question gold set does not exist
          either, so the evaluation report records the question score as absent
          rather than estimated. A working structured console is worth more than
          a text box that pretends to understand.
        </p>
        <Rule tight />
        <p className="note">
          Several of these questions cannot be expressed against the KSP schema
          at all, because they need a person key the schema does not have. Those
          are the ones worth reading.
        </p>
      </Panel>

      <Panel id="console" title="Question" eyebrow="navy">
        <div className="qpicker" role="group" aria-label="Choose a question and fill in its parameters">
          <label className="field">
            <span className="field__label">Question</span>
            <select
              className="field__control"
              value={questionId}
              onChange={(e) => setQuestionId(e.target.value)}
            >
              {QUESTIONS.map((q) => (
                <option key={q.id} value={q.id}>
                  {q.text}
                </option>
              ))}
            </select>
          </label>

          {question.params.map((param) => (
            <label className="field" key={param.key}>
              <span className="field__label">{param.label}</span>
              {param.kind === 'select' ? (
                <select
                  className="field__control"
                  value={filled[param.key] ?? ''}
                  onChange={(e) =>
                    setValues({ ...values, [`${question.id}:${param.key}`]: e.target.value })
                  }
                >
                  {optionsFor(param).map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className="field__control"
                  type="number"
                  min={param.min}
                  max={param.max}
                  value={filled[param.key] ?? ''}
                  onChange={(e) =>
                    setValues({ ...values, [`${question.id}:${param.key}`]: e.target.value })
                  }
                />
              )}
            </label>
          ))}
        </div>
      </Panel>

      {answer && (
        <>
          <Panel
            id="answer-meta"
            title="Answer"
            eyebrow={answer.rows.length ? 'resolved' : 'review'}
            aside={
              <StatusPill
                label={answer.rows.length ? 'rows returned' : 'no rows'}
                tone={answer.rows.length ? 'resolved' : 'review'}
              />
            }
          >
            <MetricRow>
              <Metric
                label="Rows returned"
                value={answer.rows.length}
                tone={answer.rows.length ? 'resolved' : 'review'}
              />
              <Metric
                label="Source"
                value={answer.source.split(',')[0] ?? ''}
                small
                caption={<>{answer.source}</>}
              />
              <Metric
                label="Identities available"
                value={n(reports.profiles?.total_identities ?? 0)}
                small
                caption={
                  <>
                    the console queries the exported top{' '}
                    {n(reports.profiles?.shown ?? 0)} profiles, not the whole
                    corpus
                  </>
                }
              />
            </MetricRow>
            {answer.note && (
              <>
                <Rule />
                <p className="note">{answer.note}</p>
              </>
            )}
          </Panel>

          <Panel id="sql" title="Equivalent SQL" eyebrow="official">
            <p className="note">
              What this question would be against the KSP schema plus the{' '}
              <span className="mono">ResolvedIdentity</span> table SUTRA adds.
              The rows above were computed over the exported JSON, so this SQL
              is shown for audit and is not what executed.
            </p>
            <pre className="sql">{answer.sql}</pre>
          </Panel>

          <Panel id="rows" title="Rows" eyebrow="signal" flush>
            {answer.rows.length ? (
              <DataTable
                caption={`${answer.rows.length} rows from ${answer.source}.`}
                columns={answer.columns}
                rows={answer.rows}
                rowKey={(r, i) => `${r[answer.columns[0]!.key] ?? i}-${i}`}
              />
            ) : (
              <p className="note" style={{ padding: 'var(--s-4)' }}>
                No rows match. That is an answer, not an error.
              </p>
            )}
          </Panel>
        </>
      )}

      <QuestionSet reports={reports} />
    </>
  )
}

/**
 * The 150 question investigator set, and what share of it this schema can
 * answer at all.
 *
 * The deck claimed 150 questions at 74 per cent correct. The set now exists and
 * the accuracy figure still does not, because answering these from free text
 * needs a language layer nobody here has built. What is reported is coverage,
 * and the interesting band is the one that no interface could ever reach.
 */
function QuestionSet({ reports }: { reports: Reports }) {
  const feed = reports.questions
  const [shape, setShape] = useState<string>('all')

  if (!feed) {
    return (
      <Panel id="questions" title="The 150 question set" eyebrow="review">
        <p className="note">
          Not exported. Run <span className="mono">make questions</span> to score
          <span className="mono"> eval/gold/questions.yaml</span>.
        </p>
      </Panel>
    )
  }

  const impossible = feed.coverage.impossible_on_raw_schema
  const today = feed.coverage.answerable_today
  const layer = feed.coverage.needs_language_layer

  const shapes = Object.keys(feed.by_shape).sort()
  const rows = feed.questions.filter(
    (q) => shape === 'all' || q.shape === shape,
  )

  const BAND_TONE: Record<string, 'resolved' | 'review' | 'conflict'> = {
    answerable_today: 'resolved',
    needs_language_layer: 'review',
    impossible_on_raw_schema: 'conflict',
  }
  const BAND_WORD: Record<string, string> = {
    answerable_today: 'answerable now',
    needs_language_layer: 'needs a language layer',
    impossible_on_raw_schema: 'impossible on the raw schema',
  }

  const columns: Column<(typeof rows)[number]>[] = [
    { key: 'id', header: 'ID', code: true, render: (r) => r.id },
    {
      key: 'question',
      header: 'Question',
      render: (r) => (
        <>
          <div>{r.question}</div>
          {r.question_kn && <div className="kn qset__kn">{r.question_kn}</div>}
        </>
      ),
    },
    { key: 'difficulty', header: 'Difficulty', render: (r) => r.difficulty },
    {
      key: 'band',
      header: 'Reachable',
      render: (r) => (
        <StatusPill label={BAND_WORD[r.band]!} tone={BAND_TONE[r.band]!} />
      ),
    },
  ]

  return (
    <>
      <Panel
        id="questions"
        title="The 150 question investigator set"
        eyebrow="conflict"
        aside={<StatusPill label="coverage measured, accuracy not" tone="official" />}
        note={
          <>
            Questions a Karnataka investigating officer or an SCRB analyst would
            actually ask, each with gold SQL against the KSP schema. The deck
            claimed 150 questions at 74 per cent correct. The set now exists.
            The accuracy figure does not, and is not repeated here, because
            answering these from free text needs a natural language layer that
            is not built.
          </>
        }
      >
        <div className="hero" style={{ padding: 0 }}>
          <MethodBars
            methods={[
              { name: 'Answerable now', value: today!.questions },
              { name: 'Needs a language layer', value: layer!.questions },
              {
                name: 'Impossible on the raw schema',
                value: impossible!.questions,
                lead: true,
              },
            ]}
            format={(v) => String(v)}
            caption={`Of ${feed.total_questions} questions, ${today!.questions} answerable now, ${layer!.questions} need a language layer, ${impossible!.questions} impossible on the raw schema.`}
          />
          <HeroFigure
            label="Need a cross FIR person key"
            value={`${feed.headline.requires_person_key} / ${feed.total_questions}`}
            tone="conflict"
            caption={
              <>
                {(feed.headline.share_requiring_person_key * 100).toFixed(1)}% of
                the question set cannot be answered on the KSP schema as
                supplied, at any level of interface sophistication, because the
                schema has no person entity spanning FIRs. This is the gap
                measured from the question side rather than from the column
                side.
              </>
            }
          />
        </div>
        <Rule />
        <MetricRow>
          <Metric
            label="Questions"
            value={feed.total_questions}
            small
            caption={<>with gold SQL, in eval/gold/questions.yaml</>}
          />
          <Metric
            label="With a Kannada rendering"
            value={feed.kannada.questions_with_kannada}
            small
            tone="signal"
            caption={<>the ones an officer would ask aloud at a counter</>}
          />
          <Metric
            label="Accuracy"
            value="not measured"
            small
            tone="conflict"
            caption={<>no language layer exists to run the set through</>}
          />
        </MetricRow>
      </Panel>

      <Panel
        id="questions-shape"
        title="Which kinds of question the schema cannot answer"
        eyebrow="signal"
        flush
      >
        <DataTable
          caption="Investigative shape against the share of its questions needing a cross FIR person key. The shapes at the top are the ones the KSP schema cannot serve at all."
          columns={[
            { key: 'shape', header: 'Shape', render: (r) => r.shape.replace(/_/g, ' ') },
            { key: 'n', header: 'Questions', numeric: true, render: (r) => String(r.questions) },
            {
              key: 'pk',
              header: 'Need the person key',
              numeric: true,
              render: (r) => (
                <span className="value--conflict">{r.requires_person_key}</span>
              ),
            },
            {
              key: 'share',
              header: 'Share',
              numeric: true,
              render: (r) => (
                <>
                  {(r.share_needing_person_key * 100).toFixed(0)}%
                  <Bar fraction={r.share_needing_person_key} tone="review" />
                </>
              ),
            },
          ]}
          rows={shapes
            .map((s) => ({ shape: s, ...feed.by_shape[s]! }))
            .sort((a, b) => b.share_needing_person_key - a.share_needing_person_key)}
          rowKey={(r) => r.shape}
        />
      </Panel>

      <Panel id="questions-list" title="Every question" eyebrow="official" flush>
        <div style={{ padding: 'var(--s-4)' }}>
          <label className="field">
            <span className="field__label">Filter by shape</span>
            <select
              className="field__control"
              value={shape}
              onChange={(e) => setShape(e.target.value)}
            >
              <option value="all">All {feed.total_questions}</option>
              {shapes.map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, ' ')} ({feed.by_shape[s]!.questions})
                </option>
              ))}
            </select>
          </label>
        </div>
        <DataTable
          caption="Every question in the set, with its difficulty and whether any interface over the raw KSP schema could reach it. Gold SQL for each is in eval/gold/questions.yaml."
          columns={columns}
          rows={rows}
          rowKey={(r) => r.id}
        />
      </Panel>
    </>
  )
}
