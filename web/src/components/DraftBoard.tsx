import type { ChampionInfo } from '../api/client.ts'
import { actor, kind, TEMPLATE } from '../draftOrder.ts'
import { ChampionIcon } from './ChampionIcon.tsx'

type Slot = { index: number; champion: string | undefined }

function slotsFor(side: 'us' | 'them', what: 'ban' | 'pick', actions: string[], wePickFirst: boolean): Slot[] {
  return TEMPLATE.map((_, i) => i)
    .filter((i) => actor(i, wePickFirst) === side && kind(i) === what)
    .map((i) => ({ index: i, champion: actions[i] }))
}

function SlotView({
  slot,
  current,
  byName,
  big,
}: {
  slot: Slot
  current: number
  byName: Map<string, ChampionInfo>
  big: boolean
}) {
  const size = big ? 36 : 26
  const active = slot.index === current
  let label = 'skipped'
  if (slot.champion === undefined) {
    label = active ? 'now' : '—'
  } else if (slot.champion) {
    label = slot.champion
  }
  return (
    <li
      title={slot.champion || undefined}
      aria-current={active ? 'step' : undefined}
      className={`flex items-center gap-2 rounded-md border px-1.5 py-1 text-xs ${active ? 'border-accent bg-surface-2' : 'border-line'}`}
    >
      <span className="w-5 text-right text-muted tabular">{slot.index + 1}</span>
      <ChampionIcon championKey={slot.champion ? (byName.get(slot.champion)?.key ?? null) : null} size={size} />
      <span className={big ? `truncate ${slot.champion ? 'font-medium' : 'text-muted'}` : 'sr-only'}>{label}</span>
    </li>
  )
}

/** Both teams' bans and picks in pro order; the slot being decided is highlighted (amber). */
export function DraftBoard({
  actions,
  wePickFirst,
  weAreBlue,
  ourName,
  theirName,
  byName,
}: {
  actions: string[]
  wePickFirst: boolean
  weAreBlue: boolean
  ourName: string
  theirName: string
  byName: Map<string, ChampionInfo>
}) {
  const current = actions.length
  const ours = { side: 'us' as const, name: ourName, colour: weAreBlue ? 'blue' : 'red' }
  const theirs = { side: 'them' as const, name: theirName, colour: weAreBlue ? 'red' : 'blue' }
  const sides = weAreBlue ? [ours, theirs] : [theirs, ours] // blue always on the left
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {sides.map((s) => (
        <section
          key={s.side}
          aria-label={`${s.name} (${s.colour} side)`}
          className="rounded-lg border border-line bg-surface p-3"
        >
          <h2 className="mb-2 flex items-center justify-between text-sm font-semibold">
            <span>{s.name}</span>
            <span className={`rounded px-1.5 text-xs ${s.colour === 'blue' ? 'bg-primary-soft' : 'bg-surface-2'}`}>
              {s.colour} side{s.side === 'us' ? ' · us' : ''}
            </span>
          </h2>
          <p className="mb-1 text-xs text-muted">Bans</p>
          <ol className="mb-2 grid grid-cols-5 gap-1">
            {slotsFor(s.side, 'ban', actions, wePickFirst).map((slot) => (
              <SlotView key={slot.index} slot={slot} current={current} byName={byName} big={false} />
            ))}
          </ol>
          <p className="mb-1 text-xs text-muted">Picks</p>
          <ol className="space-y-1">
            {slotsFor(s.side, 'pick', actions, wePickFirst).map((slot) => (
              <SlotView key={slot.index} slot={slot} current={current} byName={byName} big={true} />
            ))}
          </ol>
        </section>
      ))}
    </div>
  )
}
