/**
 * Hierarchy primitives.
 *
 * Each route gets exactly one of these at roughly double the visual weight of
 * everything around it. Nothing here introduces a colour or a typeface, and
 * every figure is passed in already computed from the exported JSON.
 */

import { useEffect, useState, type ReactNode } from 'react'

import { useT } from '../i18n/useLanguage'
import { useScope } from '../scope/useScope'

export type HeroTone = 'resolved' | 'conflict' | 'review' | 'navy'

/* ---------------------------------------------------------- hero figure */

/** The one very large number on a route. Display face, tabular figures. */
export function HeroFigure({
  value,
  caption,
  label,
  tone = 'resolved',
}: {
  value: string
  caption: ReactNode
  label?: string
  tone?: HeroTone
}) {
  return (
    <div>
      {label && <span className="hero__label">{label}</span>}
      <span className={`hero__figure hero__figure--${tone}`}>{value}</span>
      <p className="hero__caption">{caption}</p>
    </div>
  )
}

/** A hero sized readout used inside an otherwise ordinary panel. */
export function Readout({
  label,
  value,
  caption,
  tone,
}: {
  label: string
  value: string
  caption?: ReactNode
  tone?: 'resolved' | 'conflict' | 'review'
}) {
  return (
    <div className="metric">
      <span className="metric__label">{label}</span>
      <span className={`readout${tone ? ` readout--${tone}` : ''}`}>{value}</span>
      {caption && <span className="metric__caption">{caption}</span>}
    </div>
  )
}

/* ----------------------------------------------------------- method bars */

export type Method = { name: string; value: number; lead?: boolean }

/**
 * Proportional bars, drawn to scale and grown once on mount.
 *
 * The growth is the point. A static bar chart states the comparison, a bar
 * that arrives makes the reader watch it happen. It runs once and never
 * again, and under prefers-reduced-motion the duration token collapses to
 * zero so the bars are simply present.
 */
export function MethodBars({
  methods,
  format = (v) => v.toFixed(4),
  caption,
}: {
  methods: Method[]
  format?: (value: number) => string
  caption?: string
}) {
  const [grown, setGrown] = useState(false)
  const max = Math.max(...methods.map((m) => m.value), 1e-9)

  useEffect(() => {
    const frame = requestAnimationFrame(() => setGrown(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  return (
    <div
      className="methods"
      role="img"
      aria-label={
        caption ??
        methods.map((m) => `${m.name} ${format(m.value)}`).join(', ')
      }
    >
      {methods.map((method) => (
        <div
          className={`method${method.lead ? ' method--lead' : ''}`}
          key={method.name}
        >
          <span className="method__name">{method.name}</span>
          <span className="method__track">
            <span
              className="method__fill"
              style={{ width: grown ? `${(method.value / max) * 100}%` : '0%' }}
            />
          </span>
          <span className="method__value">{format(method.value)}</span>
        </div>
      ))}
    </div>
  )
}

/* -------------------------------------------------------- sticky subhead */

export type Stat = {
  label: string
  value: string
  tone?: 'resolved' | 'conflict' | 'review'
}

/** Thin sticky bar carrying a route's defining numbers, so scrolling never
 *  loses the context. */
export function SubHeader({ title, stats }: { title: string; stats: Stat[] }) {
  const t = useT()
  const scope = useScope()
  return (
    <div className="subhead">
      <span className="subhead__title">{t(title)}</span>
      {/* Every screen states the scope it is rendering under, in the same
          place, whether or not anything is being filtered. A reader should
          never have to look at the masthead to know what they are seeing. */}
      <span
        className={`subhead__scope${scope.filtering ? ' subhead__scope--on' : ''}`}
      >
        {scope.describe}
      </span>
      {stats.map((stat) => (
        <span className="subhead__stat" key={stat.label}>
          <span className="subhead__label">{t(stat.label)}</span>
          <span
            className={`subhead__value${stat.tone ? ` subhead__value--${stat.tone}` : ''}`}
          >
            {stat.value}
          </span>
        </span>
      ))}
    </div>
  )
}

/* -------------------------------------------------------------- details */

/** Secondary content, present and open but visually quiet. */
export function Details({
  summary,
  children,
  open = true,
}: {
  summary: string
  children: ReactNode
  open?: boolean
}) {
  return (
    <details className="details" open={open}>
      <summary>{summary}</summary>
      <div className="details__body">{children}</div>
    </details>
  )
}

/* ------------------------------------------------------------ skeleton */

export function Skeleton({ lines = 3, figure = false }: { lines?: number; figure?: boolean }) {
  return (
    <div aria-hidden="true">
      {figure && <div className="skeleton skeleton--figure" />}
      {Array.from({ length: lines }).map((_, i) => (
        <div
          className="skeleton skeleton--line"
          key={i}
          style={{ width: `${100 - i * 12}%` }}
        />
      ))}
    </div>
  )
}

export function SkeletonBars({ rows = 5 }: { rows?: number }) {
  return (
    <div aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          className="skeleton skeleton--bar"
          key={i}
          style={{ width: `${30 + i * 14}%` }}
        />
      ))}
    </div>
  )
}
