/**
 * Persistent chrome. Masthead, provenance bar, left rail.
 *
 * The provenance bar sits under the masthead on every route rather than being
 * a property of one screen, because provenance is a property of the whole
 * surface. A printed page from any route carries where its numbers came from.
 */

import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { AuditStrip, ProvenanceBar, StatusPill } from './primitives'
import { Search } from './Search'
import { SOURCES, timestamp } from '../data/useReports'
import { LANGUAGES } from '../i18n/strings'
import { useLanguage } from '../i18n/useLanguage'
import { ROLES, useScope, type RoleId } from '../scope/useScope'
import type { Reports } from '../data/types'

export const ROUTES = [
  { path: '/', label: 'Corpus audit', hint: 'what the data contains' },
  { path: '/evaluation', label: 'Evaluation', hint: 'measured against ground truth' },
  { path: '/identities', label: 'Review queue', hint: 'merges awaiting a decision' },
  { path: '/network', label: 'Offender network', hint: 'resolved identities' },
  { path: '/cases', label: 'Undetected cases', hint: 'ranked candidates' },
  { path: '/hotspots', label: 'Hotspots', hint: 'offender density, not case density' },
  { path: '/ask', label: 'Query console', hint: 'structured, no LLM' },
  { path: '/audit', label: 'Audit trail', hint: 'what the run did' },
  { path: '/status', label: 'Build status', hint: 'every claim, checked' },
] as const

const UNBUILT = new Set<string>([])

/**
 * English or Kannada, in the masthead where a government portal puts it.
 *
 * Two buttons rather than a select, because a select hides the alternative
 * behind an interaction and there are only two. `aria-pressed` carries the
 * state, so it is never colour alone.
 */
function LanguageToggle() {
  const { language, setLanguage, t } = useLanguage()
  return (
    <div className="langswitch" role="group" aria-label={t('Language')}>
      <span className="langswitch__label">{t('Language')}</span>
      {LANGUAGES.map((option) => (
        <button
          key={option.code}
          type="button"
          lang={option.code}
          className={`langswitch__btn${
            language === option.code ? ' langswitch__btn--on' : ''
          }`}
          aria-pressed={language === option.code}
          onClick={() => setLanguage(option.code)}
        >
          {option.native}
        </button>
      ))}
    </div>
  )
}

/**
 * Role and jurisdiction, chosen in the masthead.
 *
 * A select rather than buttons, because there are four roles and one of them
 * carries a second choice. The district picker appears only for the role that
 * is district scoped, so the control shows the shape of the access model.
 */
function RolePicker({ districts }: { districts: string[] }) {
  const { role, district, setRole, setDistrict, t } = {
    ...useScope(),
    t: useLanguage().t,
  }
  return (
    <div className="rolepick" role="group" aria-label={t('Role and jurisdiction')}>
      <span className="rolepick__label">{t('Role')}</span>
      <select
        className="rolepick__select"
        value={role.id}
        aria-label={t('Role')}
        onChange={(e) => setRole(e.target.value as RoleId)}
      >
        {ROLES.map((r) => (
          <option key={r.id} value={r.id}>
            {t(r.label)}
          </option>
        ))}
      </select>
      {role.districtScoped && (
        <select
          className="rolepick__select"
          value={district ?? ''}
          aria-label={t('District')}
          onChange={(e) => setDistrict(e.target.value)}
        >
          {districts.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      )}
    </div>
  )
}

export function Shell({
  reports,
  districts,
}: {
  reports: Reports
  districts: string[]
}) {
  const { manifest, blocking, evaluation, runlog } = reports
  const { pathname } = useLocation()
  const { t } = useLanguage()
  const scope = useScope()

  const provenance = [
    { key: 'run', value: runlog?.run_id ?? 'not exported' },
    { key: 'seed', value: String(manifest.seed) },
    { key: 'corpus', value: timestamp(manifest.generated_at) },
    { key: 'blocking', value: blocking ? timestamp(blocking.generated_at) : 'not run' },
    { key: 'eval', value: evaluation ? timestamp(evaluation.generated_at) : 'not run' },
    { key: 'preset', value: manifest.co_offending_preset ?? 'unknown' },
    { key: 'read', value: SOURCES.corpus },
    ...(evaluation ? [{ key: 'read', value: SOURCES.evaluation }] : []),
    { key: 'role', value: scope.describe },
  ]

  return (
    <>
      <div className="shell">
        <div className="masthead-block">
          <header className="masthead">
            <div>
              <p className="masthead__org">{t('Karnataka State Police')}</p>
              <h1 className="masthead__mark">SUTRA</h1>
              <p className="masthead__bureau">{t('State Crime Records Bureau')}</p>
              {/* Prose stays in English. See web/src/i18n/strings.ts for why. */}
              <p className="masthead__screen">
                Identity resolution for the KSP crime record. The FIR schema
                carries no cross case person identity, so this system builds it
                and measures how much it recovers.
              </p>
            </div>
            <div className="masthead__right">
              <Search reports={reports} />
              <RolePicker districts={districts} />
              <LanguageToggle />
              <StatusPill
                label={scope.filtering ? 'view scoped' : 'no scope applied'}
                tone={scope.filtering ? 'signal' : 'official'}
              />
              <StatusPill
                label={evaluation ? 'layers 1 to 7 measured' : 'evaluation not run'}
                tone={evaluation ? 'resolved' : 'review'}
              />
              <StatusPill label="synthetic corpus" tone="review" />
              <StatusPill label="read only surface" tone="official" />
            </div>
          </header>
          <ProvenanceBar entries={provenance} />
        </div>

        <div className="layout">
          <nav className="rail" aria-label={t('Sections')}>
            <ul>
              {ROUTES.filter((route) => scope.allows(route.path)).map((route) => (
                <li key={route.path}>
                  <NavLink
                    to={route.path}
                    end={route.path === '/'}
                    className={({ isActive }) =>
                      `rail__link${isActive ? ' rail__link--active' : ''}` +
                      (UNBUILT.has(route.path) ? ' rail__link--unbuilt' : '')
                    }
                  >
                    <span className="rail__label">{t(route.label)}</span>
                    <span className="rail__hint">{t(route.hint)}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          {/* Keyed on the path so each route fades in. Opacity only, 150ms,
              no slide. The key is what restarts the animation. */}
          <main id="main" className="stack content route-fade" key={pathname}>
            <Outlet />
          </main>
        </div>
      </div>

      <AuditStrip
        entries={[
          { key: 'run', value: runlog?.run_id ?? 'not exported' },
          { key: 'seed', value: String(manifest.seed) },
          { key: 'corpus', value: timestamp(manifest.generated_at) },
          { key: 'preset', value: manifest.co_offending_preset ?? 'unknown' },
          // The role in force travels with the provenance, because a figure
          // read under a scope is a different figure from the same one read
          // statewide, and a printed page has to say which it was.
          { key: 'role', value: scope.describe },
        ]}
      />
    </>
  )
}
