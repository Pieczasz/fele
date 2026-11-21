import type { DraftAdvice, OptionOut } from '../api/client.ts'
import { pct } from '../format.ts'
import { ChampionIcon } from './ChampionIcon.tsx'
import { Section } from './QueryState.tsx'

function WinProbBar({ mean, p10, p90, note }: { mean: number; p10: number; p90: number; note: string }) {
  return (
    <div title={note}>
      <div className="mb-1 flex justify-between text-sm">
        <span className="font-semibold">Our win probability {pct(mean)}</span>
        <span className="text-muted tabular">
          range {pct(p10)}–{pct(p90)}
        </span>
      </div>
      <meter className="sr-only" min={0} max={1} value={mean}>
        {`${pct(mean)}, likely between ${pct(p10)} and ${pct(p90)}`}
      </meter>
      <div aria-hidden="true" className="relative h-3 rounded-full bg-surface-2">
        <span
          className="absolute inset-y-0 rounded-full bg-primary/30"
          style={{ left: `${p10 * 100}%`, width: `${(p90 - p10) * 100}%` }}
        />
        <span className="absolute inset-y-0 w-1 rounded bg-primary" style={{ left: `calc(${mean * 100}% - 2px)` }} />
        <span className="absolute -inset-y-1 w-px bg-ink/40" style={{ left: '50%' }} />
      </div>
      <p className="mt-1 text-xs text-muted">{note}</p>
    </div>
  )
}

function OptionRow({ o, rank, onPick }: { o: OptionOut; rank: number; onPick: (c: string) => void }) {
  return (
    <li className="rounded-md border border-line p-2">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onPick(o.champion)}
          className="flex flex-1 cursor-pointer items-center gap-2 text-left"
          title={`Take ${o.champion} (key ${rank})`}
        >
          <kbd className="rounded border border-line px-1 text-xs text-muted">{rank}</kbd>
          <ChampionIcon championKey={o.key} size={32} />
          <span className="font-semibold">{o.champion}</span>
          {o.role ? <span className="text-xs capitalize text-muted">{o.role}</span> : null}
        </button>
        {o.win_prob === null ? null : <span className="text-sm tabular">{pct(o.win_prob, 1)}</span>}
      </div>
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-muted">
        {o.reasons.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
    </li>
  )
}

function CompView({ title, comp }: { title: string; comp: DraftAdvice['our_comp'] }) {
  if (comp.champions.length === 0) {
    return null
  }
  return (
    <div className="text-xs">
      <p className="font-semibold">{title}</p>
      <p className="text-muted">
        {comp.damage} damage ({pct(comp.ap_share)} magic) · {comp.scaling} game · engage {comp.totals.engage ?? 0} ·
        frontline {comp.totals.frontline ?? 0} · peel {comp.totals.peel ?? 0}
      </p>
      {comp.warnings.map((w) => (
        <p key={w} className="text-bad">
          ⚠ {w}
        </p>
      ))}
    </div>
  )
}

/** Our turn: ranked options with reasons. Their turn: what they most likely do. Plus win probability and comps. */
export function AdvicePanel({
  advice,
  onPick,
  busy,
}: {
  advice: DraftAdvice | undefined
  onPick: (c: string) => void
  busy: boolean
}) {
  if (!advice) {
    return <p className="text-muted">{busy ? 'Thinking…' : 'Pick an opponent to start.'}</p>
  }
  const ourTurn = advice.next?.who === 'us'
  return (
    <div className={`space-y-4 motion-safe:transition-opacity ${busy ? 'opacity-60' : ''}`} aria-busy={busy}>
      {busy ? (
        <p role="status" className="text-xs text-muted">
          Updating for the new draft state…
        </p>
      ) : null}
      <WinProbBar {...advice.win_prob} />
      {advice.next ? (
        <Section
          title={ourTurn ? `Options for our ${advice.next.kind}` : `They ${advice.next.kind} next — most likely`}
          hint={ourTurn ? 'Ranked options, not orders: read the reasons' : 'draft model, their perspective'}
        >
          {ourTurn ? (
            <ol className="space-y-2">
              {advice.options.map((o, i) => (
                <OptionRow key={o.champion} o={o} rank={i + 1} onPick={onPick} />
              ))}
            </ol>
          ) : (
            <ol className="space-y-1">
              {advice.likely.map((l, i) => (
                <li key={l.champion}>
                  <button
                    type="button"
                    onClick={() => onPick(l.champion)}
                    className="flex w-full cursor-pointer items-center gap-2 rounded px-1 hover:bg-surface-2"
                  >
                    <kbd className="rounded border border-line px-1 text-xs text-muted">{i + 1}</kbd>
                    <ChampionIcon championKey={l.key} size={28} />
                    <span className="flex-1 text-left">{l.champion}</span>
                    <span className="text-sm tabular text-muted">{pct(l.probability)}</span>
                  </button>
                </li>
              ))}
            </ol>
          )}
        </Section>
      ) : (
        <p className="font-semibold">Draft complete.</p>
      )}
      <div className="space-y-2">
        <CompView title="Our comp" comp={advice.our_comp} />
        <CompView title="Their comp" comp={advice.their_comp} />
      </div>
    </div>
  )
}
