/**
 * Shown on routes and panels that are deliberately not built.
 *
 * Deliberately router free, so it can be imported by any screen without
 * dragging routing into the module graph. That also keeps every screen
 * renderable in isolation by the smoke test.
 *
 * The point of this component is that the surface never implies a capability
 * the engine does not have. It names what would be here, what is missing, and
 * the command that produces it.
 */

import type { ReactNode } from 'react'

import { StatusPill } from './primitives'

export function NotBuilt({
  title,
  what,
  why,
  command,
}: {
  title: string
  what: string
  why: ReactNode
  command?: string
}) {
  return (
    <section className="panel" aria-labelledby="notbuilt-title">
      <div className="panel__eyebrow panel__eyebrow--review" aria-hidden="true" />
      <header className="panel__head">
        <h2 className="panel__title" id="notbuilt-title">
          {title}
        </h2>
        <StatusPill label="not built" tone="review" />
      </header>
      <div className="panel__body">
        <p className="note">{what}</p>
        <p className="note">{why}</p>
        {command && <code className="state__cmd">{command}</code>}
      </div>
    </section>
  )
}
