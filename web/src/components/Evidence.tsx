import type { Rate } from '../api/client.ts'
import { interval, pct } from '../format.ts'

/** Sample-size badge: every number in fele shows the evidence behind it. */
export function NBadge({ k, n, unit = 'games' }: { k?: number; n: number; unit?: string }) {
  const text = k === undefined ? `n=${n}` : `${k}/${n}`
  const label = k === undefined ? `${n} ${unit}` : `${k} of ${n} ${unit}`
  return (
    <span
      className="tabular inline-block rounded border border-line bg-surface-2 px-1.5 py-px text-xs text-muted"
      title={label}
    >
      <span aria-hidden="true">{text}</span>
      <span className="sr-only">{label}</span>
    </span>
  )
}

const BAR_WIDTH = 112 // px

/**
 * A rate with its 95% interval (whisker) and, optionally, the league rate (amber tick).
 * The visible percentage and the n badge carry the meaning; the bar only supports it.
 */
export function RateBar({ rate, base, unit = 'games' }: { rate: Rate; base?: number | undefined; unit?: string }) {
  const value = rate.rate ?? 0
  const lo = rate.lo ?? value
  const hi = rate.hi ?? value
  const label = [
    `${pct(rate.rate)} (${rate.k} of ${rate.n} ${unit})`,
    `95% interval ${interval(rate.lo, rate.hi)}`,
    base === undefined ? '' : `league ${pct(base)}`,
  ]
    .filter(Boolean)
    .join(', ')
  return (
    <span className="inline-flex items-center gap-2" title={label}>
      <span className="tabular w-10 text-right font-medium">{pct(rate.rate)}</span>
      <span aria-hidden="true" className="relative h-2.5 rounded-full bg-surface-2" style={{ width: BAR_WIDTH }}>
        <span className="absolute inset-y-0 left-0 rounded-full bg-primary/70" style={{ width: value * BAR_WIDTH }} />
        <span
          className="absolute top-1/2 h-px -translate-y-1/2 bg-ink"
          style={{ left: lo * BAR_WIDTH, width: Math.max(1, (hi - lo) * BAR_WIDTH) }}
        />
        {base === undefined ? null : (
          <span className="absolute -inset-y-1 w-0.5 rounded bg-accent" style={{ left: base * BAR_WIDTH - 1 }} />
        )}
      </span>
      <NBadge k={rate.k} n={rate.n} unit={unit} />
      <span className="sr-only">{label}</span>
    </span>
  )
}

const TENDENCY = {
  strong: { text: 'Strong', className: 'border-primary text-primary', title: 'Unlikely to be chance (BH q < 0.05)' },
  weak: {
    text: 'Weak',
    className: 'border-accent text-accent',
    title: 'Could be chance (p < 0.05, not after correction)',
  },
  noise: { text: 'Noise', className: 'border-line text-muted', title: 'Indistinguishable from the league average' },
} as const

export function TendencyBadge({ tendency }: { tendency: keyof typeof TENDENCY }) {
  const t = TENDENCY[tendency]
  return (
    <span className={`rounded border px-1.5 py-px text-xs font-medium ${t.className}`} title={t.title}>
      {t.text}
    </span>
  )
}
