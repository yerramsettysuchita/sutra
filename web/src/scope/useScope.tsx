/**
 * Role and jurisdiction scoping.
 *
 * WHAT THIS IS
 *
 * A view filter. Choosing a role changes what every screen renders and changes
 * the counts to match, so a jury can see the access model behave rather than
 * read a claim that one exists.
 *
 * WHAT THIS IS NOT, AND THE DISTINCTION MATTERS
 *
 * It is not authentication and it is not enforcement. The role is chosen from a
 * dropdown by whoever is looking at the page, it is held in the browser, and
 * the underlying JSON is served in full to anyone who requests it. A user who
 * opens the network tab sees every district regardless of the role selected.
 *
 * Real enforcement means the server decides what to send, after Catalyst
 * Authentication has established who is asking. Neither is built. `/status`
 * says both plainly and this comment exists so nobody reading the source
 * mistakes a demonstration for a control.
 *
 * WHY BUILD IT AT ALL
 *
 * Because the scoping rules are the part that has to be right, and they are the
 * part a slide cannot show. An investigating officer scoped to one district
 * should see their district's cases, the identities that touch those cases, and
 * the co offender edges among those identities, with every count reduced
 * accordingly. Getting that composition right is the work. Wiring it to a real
 * session afterwards is comparatively mechanical.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export type RoleId = 'io' | 'analyst' | 'operator' | 'reviewer'

export type Role = {
  id: RoleId
  label: string
  /** What this role is for, in one line. */
  purpose: string
  /** Whether the role is confined to a single district. */
  districtScoped: boolean
  /** Route paths this role may open. An empty list means all of them. */
  routes: string[]
  /** Shown in the sub header and the audit strip. */
  scopeWord: string
  /**
   * Whether this role may accept or refuse a merge.
   *
   * This is the first difference between roles that is not filtering. An
   * investigating officer reads the queue for their district and does not
   * clear it, because approving a merge into the person record is a records
   * function rather than an investigative one.
   */
  canDecide: boolean
  /**
   * Whether this role may reverse a decision somebody else made.
   *
   * Only the reviewer. A reversal appends to the log rather than removing the
   * original, so the power is to correct the record and never to erase it.
   */
  canReverse: boolean
  /** One line on what this role can do, for the /status table. */
  can: string
}

export const ROLES: Role[] = [
  {
    id: 'analyst',
    label: 'SCRB analyst',
    purpose: 'Statewide. Every district, every screen.',
    districtScoped: false,
    routes: [],
    scopeWord: 'statewide',
    canDecide: true,
    canReverse: false,
    can: 'Decide any pair, statewide. Cannot reverse.',
  },
  {
    id: 'io',
    label: 'Investigating officer',
    purpose:
      'One district. Cases, identities and network edges touching that district only.',
    districtScoped: true,
    routes: [],
    scopeWord: 'one district',
    canDecide: false,
    canReverse: false,
    can: 'Read only, and search. Cannot decide, because clearing the queue is a records function.',
  },
  {
    id: 'operator',
    label: 'Records operator',
    purpose: 'The review queue only. No network, no profiles, no evaluation.',
    districtScoped: false,
    routes: ['/identities'],
    scopeWord: 'review queue only',
    canDecide: true,
    canReverse: false,
    can: 'Decide any pair. This is the role the queue exists for.',
  },
  {
    id: 'reviewer',
    label: 'Reviewer',
    purpose: 'Read only across the state, with the full audit trail.',
    districtScoped: false,
    routes: [],
    scopeWord: 'statewide, read only',
    canDecide: true,
    canReverse: true,
    can: 'Decide, and reverse a decision anyone made. Reversal appends, it never deletes.',
  },
]

export const ROLE_BY_ID = Object.fromEntries(ROLES.map((r) => [r.id, r])) as
  Record<RoleId, Role>

const ROLE_KEY = 'sutra.role'
const DISTRICT_KEY = 'sutra.district'

export type Scope = {
  role: Role
  /** District name the role is confined to, or null when statewide. */
  district: string | null
  setRole: (id: RoleId) => void
  setDistrict: (name: string) => void
  /** Whether a route is reachable under this role. */
  allows: (path: string) => boolean
  /** True when anything is actually being filtered out. */
  filtering: boolean
  /** The phrase every screen puts in its sub header. */
  describe: string
}

const ScopeContext = createContext<Scope | null>(null)

function stored(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export function ScopeProvider({
  children,
  districts,
  defaultRole,
  defaultDistrict,
}: {
  children: ReactNode
  /** Every district in the corpus, so the picker offers real ones. */
  districts: string[]
  /** Forces the starting role. Only the smoke render uses it. */
  defaultRole?: RoleId
  defaultDistrict?: string
}) {
  const [roleId, setRoleId] = useState<RoleId>(() => {
    if (defaultRole) return defaultRole
    const saved = stored(ROLE_KEY)
    return saved && saved in ROLE_BY_ID ? (saved as RoleId) : 'analyst'
  })
  const [district, setDistrictState] = useState<string | null>(() => {
    if (defaultDistrict) return defaultDistrict
    return stored(DISTRICT_KEY) ?? districts[0] ?? null
  })

  // A district scoped role with no district would show nothing, which reads as
  // a broken page rather than as an empty jurisdiction.
  useEffect(() => {
    if (!district && districts.length) setDistrictState(districts[0]!)
  }, [district, districts])

  const setRole = useCallback((id: RoleId) => {
    setRoleId(id)
    try {
      window.localStorage.setItem(ROLE_KEY, id)
    } catch {
      /* the session still switches */
    }
  }, [])

  const setDistrict = useCallback((name: string) => {
    setDistrictState(name)
    try {
      window.localStorage.setItem(DISTRICT_KEY, name)
    } catch {
      /* the session still switches */
    }
  }, [])

  const value = useMemo<Scope>(() => {
    const role = ROLE_BY_ID[roleId]
    const scopedDistrict = role.districtScoped ? district : null
    return {
      role,
      district: scopedDistrict,
      setRole,
      setDistrict,
      allows: (path: string) =>
        role.routes.length === 0 || role.routes.includes(path),
      filtering: Boolean(scopedDistrict) || role.routes.length > 0,
      describe: scopedDistrict
        ? `${role.label}, ${scopedDistrict}`
        : `${role.label}, ${role.scopeWord}`,
    }
  }, [roleId, district, setRole, setDistrict])

  return <ScopeContext.Provider value={value}>{children}</ScopeContext.Provider>
}

export function useScope(): Scope {
  const ctx = useContext(ScopeContext)
  if (ctx) return ctx
  // Screens render outside the provider in tests and in the smoke render.
  // Statewide with nothing filtered is the honest default.
  const role = ROLE_BY_ID.analyst
  return {
    role,
    district: null,
    setRole: () => {},
    setDistrict: () => {},
    allows: () => true,
    filtering: false,
    describe: `${role.label}, ${role.scopeWord}`,
  }
}
