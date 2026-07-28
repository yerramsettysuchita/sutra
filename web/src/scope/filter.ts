/**
 * Apply a jurisdiction to the reports.
 *
 * Everything here is a projection of data already loaded. Nothing is
 * recomputed, nothing is estimated, and no figure is invented for a district
 * that the engine did not measure.
 *
 * WHAT IS FILTERED
 *
 * Rows that belong to a place. Cases carry a district, identities carry the
 * cases they appear in, profiles carry the districts they touch, review pairs
 * carry a district on each side, and hotspot rows are per district. Counts that
 * are derived from those rows are recomputed from the filtered rows, so a
 * count on screen always matches the list beneath it.
 *
 * The co offender graph is filtered by membership rather than by place, because
 * an edge has no district of its own. A node is in scope when the identity is
 * in scope, and an edge is in scope when both of its endpoints are. An edge
 * with one endpoint outside the district is dropped rather than half drawn,
 * and the dropped count is reported so the reader knows the neighbourhood is
 * cut rather than absent.
 *
 * WHAT IS DELIBERATELY NOT FILTERED
 *
 * The evaluation report, the canonical headline, the vocabulary sweep, the
 * scale study and the question set. These are measurements of the engine over
 * the whole corpus, not records belonging to a place. Precision for one
 * district is not a number this project has computed, and slicing a corpus wide
 * F1 by district would produce a figure that looks like a measurement and is
 * not one. The evaluation screen says so when a scope is active.
 */

import type {
  CasesFeed,
  IdentityFeed,
  NetworkFeed,
  ProfilesFeed,
  Reports,
  RoutingFeed,
  HotspotsFeed,
} from '../data/types'

export type ScopeEffect = {
  /** What the filter removed, so a screen can say so rather than look empty. */
  identities: { before: number; after: number }
  cases: { before: number; after: number }
  edges: { before: number; after: number; cutAtBoundary: number }
  reviewPairs: { before: number; after: number }
}

export type Scoped = { reports: Reports; effect: ScopeEffect | null }

/** Identities with at least one case in the district. */
function identitiesInDistrict(reports: Reports, district: string): Set<string> {
  const inScope = new Set<string>()
  for (const identity of reports.identities?.identities ?? []) {
    if (identity.cases.some((c) => c.district === district)) {
      inScope.add(identity.identity)
    }
  }
  for (const profile of reports.profiles?.profiles ?? []) {
    if ((profile.districts ?? []).some((d) => d.district === district)) {
      inScope.add(profile.identity)
    }
  }
  return inScope
}

export function applyScope(reports: Reports, district: string | null): Scoped {
  if (!district) return { reports, effect: null }

  const inScope = identitiesInDistrict(reports, district)

  const identities: IdentityFeed | null = reports.identities && {
    ...reports.identities,
    identities: reports.identities.identities
      .filter((i) => inScope.has(i.identity))
      // A record from another district is not this officer's to read, so the
      // case list inside an identity is filtered too, and the counts beside it
      // are recomputed rather than left describing the unfiltered row.
      .map((i) => {
        const cases = i.cases.filter((c) => c.district === district)
        return {
          ...i,
          cases,
          case_count: cases.length,
          record_count: cases.length,
        }
      }),
  }
  if (identities) {
    identities.total_identities = identities.identities.length
    identities.shown = identities.identities.length
  }

  const profiles: ProfilesFeed | null = reports.profiles && {
    ...reports.profiles,
    profiles: reports.profiles.profiles.filter((p) => inScope.has(p.identity)),
  }
  if (profiles) profiles.total_identities = profiles.profiles.length

  const nodes = (reports.network?.nodes ?? []).filter((n) =>
    inScope.has(n.identity),
  )
  const nodeIds = new Set(nodes.map((n) => n.identity))
  const allEdges = reports.network?.edges ?? []
  const edges = allEdges.filter(
    (e) => nodeIds.has(e.source) && nodeIds.has(e.target),
  )
  // An edge with exactly one end inside the district. The relationship is real
  // and the officer cannot see the other end of it.
  const cutAtBoundary = allEdges.filter(
    (e) => nodeIds.has(e.source) !== nodeIds.has(e.target),
  ).length

  const network: NetworkFeed | null = reports.network && {
    ...reports.network,
    nodes,
    edges,
    recovered_edges: edges.filter((e) => e.recovered).length,
    pre_existing_edges: edges.filter((e) => !e.recovered).length,
  }

  const casesFeed: CasesFeed | null = reports.cases && {
    ...reports.cases,
    cases: reports.cases.cases.filter((c) => c.district === district),
  }

  const routing: RoutingFeed | null = reports.routing && {
    ...reports.routing,
    pairs: reports.routing.pairs.filter(
      (p) => p.left.district === district || p.right.district === district,
    ),
  }
  if (routing) {
    routing.shown = routing.pairs.length
    routing.total_in_review_band = routing.pairs.length
  }

  // District rows filter cleanly. The grid does not: a cell is a latitude and
  // longitude bucket with no district on it, and buckets straddle boundaries.
  // Clipping it would need district polygons the corpus does not carry, so the
  // grid is left statewide and the hotspots screen says which of its two views
  // is scoped and which is not. Inventing a boundary would be worse than
  // saying there is not one.
  const hotspots: HotspotsFeed | null = reports.hotspots && {
    ...reports.hotspots,
    districts: reports.hotspots.districts.filter((d) => d.district === district),
  }

  return {
    reports: {
      ...reports,
      identities,
      profiles,
      network,
      cases: casesFeed,
      routing,
      hotspots,
    },
    effect: {
      identities: {
        before: reports.identities?.identities.length ?? 0,
        after: identities?.identities.length ?? 0,
      },
      cases: {
        before: reports.cases?.cases.length ?? 0,
        after: casesFeed?.cases.length ?? 0,
      },
      edges: { before: allEdges.length, after: edges.length, cutAtBoundary },
      reviewPairs: {
        before: reports.routing?.pairs.length ?? 0,
        after: routing?.pairs.length ?? 0,
      },
    },
  }
}
