import { useId, useState } from 'react'
import type { Preferences } from '../api/client.ts'
import { Section } from '../components/QueryState.tsx'
import { useChampions, usePrefs } from '../hooks.ts'
import { download } from '../store.ts'

type PlayerPrefs = Preferences['players'][number]
type Comfort = NonNullable<NonNullable<PlayerPrefs['pool']>[number]['comfort']>
const COMFORTS: Comfort[] = ['signature', 'comfortable', 'playable', 'learning', 'refuses']
const STYLES = ['early', 'scaling', 'skirmish', 'teamfight', 'pick', 'poke', 'siege', 'split', 'protect']

function ChampionList({
  label,
  values,
  onChange,
  listId,
  known,
}: {
  label: string
  values: string[]
  onChange: (v: string[]) => void
  listId: string
  known: ReadonlyMap<string, unknown>
}) {
  const [draft, setDraft] = useState('')
  return (
    <div className="space-y-1 text-sm">
      <p className="text-xs text-muted">{label}</p>
      <ul className="flex flex-wrap gap-1">
        {values.map((c) => (
          <li key={c} className="flex items-center gap-1 rounded border border-line px-1.5">
            {c}
            <button
              type="button"
              aria-label={`Remove ${c}`}
              onClick={() => onChange(values.filter((v) => v !== c))}
              className="cursor-pointer text-muted"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      <input
        list={listId}
        aria-label={`Add to ${label}`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && known.has(draft) && !values.includes(draft)) {
            onChange([...values, draft])
            setDraft('')
          }
        }}
        placeholder="champion, then Enter"
        className="min-h-8 w-44 rounded border border-line bg-bg px-2"
      />
    </div>
  )
}

function PlayerEditor({
  player,
  onChange,
  listId,
  known,
}: {
  player: PlayerPrefs
  onChange: (p: PlayerPrefs) => void
  listId: string
  known: ReadonlyMap<string, unknown>
}) {
  const pool = player.pool ?? []
  const [champion, setChampion] = useState('')
  return (
    <article className="rounded-lg border border-line bg-surface p-3">
      <header className="mb-2 flex items-center justify-between">
        <h3 className="font-semibold">
          {player.name} <span className="text-sm font-normal capitalize text-muted">{player.role}</span>
        </h3>
        <label className="flex items-center gap-1 text-xs">
          <input
            type="checkbox"
            checked={player.wants_prio ?? false}
            onChange={(e) => onChange({ ...player, wants_prio: e.target.checked })}
          />
          wants priority picks
        </label>
      </header>
      <table className="mb-2 w-full text-sm">
        <caption className="sr-only">{player.name}'s champion pool</caption>
        <tbody className="divide-y divide-line">
          {pool.map((c, i) => (
            <tr key={c.champion}>
              <th scope="row" className="py-1 text-left font-normal">
                {c.champion}
              </th>
              <td>
                <select
                  aria-label={`${c.champion} comfort`}
                  value={c.comfort ?? 'comfortable'}
                  onChange={(e) =>
                    onChange({
                      ...player,
                      pool: pool.map((x, j) => (j === i ? { ...x, comfort: e.target.value as Comfort } : x)),
                    })
                  }
                  className="rounded border border-line bg-bg px-1"
                >
                  {COMFORTS.map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </td>
              <td>
                <input
                  aria-label={`${c.champion} note`}
                  value={c.note ?? ''}
                  onChange={(e) =>
                    onChange({ ...player, pool: pool.map((x, j) => (j === i ? { ...x, note: e.target.value } : x)) })
                  }
                  className="w-full rounded border border-line bg-bg px-1"
                />
              </td>
              <td className="text-right">
                <button
                  type="button"
                  aria-label={`Remove ${c.champion}`}
                  onClick={() => onChange({ ...player, pool: pool.filter((_, j) => j !== i) })}
                  className="cursor-pointer text-muted"
                >
                  ×
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mb-2 flex gap-2 text-sm">
        <input
          list={listId}
          aria-label={`Add a champion to ${player.name}'s pool`}
          value={champion}
          onChange={(e) => setChampion(e.target.value)}
          placeholder="add champion"
          className="min-h-8 rounded border border-line bg-bg px-2"
        />
        <button
          type="button"
          disabled={!known.has(champion) || pool.some((c) => c.champion === champion)}
          onClick={() => {
            onChange({ ...player, pool: [...pool, { champion, comfort: 'comfortable', note: '' }] })
            setChampion('')
          }}
          className="min-h-8 cursor-pointer rounded border border-line px-2 disabled:opacity-40"
        >
          Add
        </button>
      </div>
      <ChampionList
        label="Hates playing against"
        values={player.hates_playing_against ?? []}
        onChange={(v) => onChange({ ...player, hates_playing_against: v })}
        listId={listId}
        known={known}
      />
    </article>
  )
}

export function CoachPage() {
  const [prefs, setPrefs, reset] = usePrefs()
  const champions = useChampions()
  const listId = useId()
  const [opponent, setOpponent] = useState('')
  if (!prefs) {
    return (
      <p role="status" className="text-muted">
        Loading coach inputs…
      </p>
    )
  }
  const strategy = prefs.strategy ?? {}
  const setStrategy = (s: Partial<NonNullable<Preferences['strategy']>>) =>
    setPrefs({ ...prefs, strategy: { ...strategy, ...s } })
  const mustBan = strategy.must_ban_vs_opponent ?? {}
  return (
    <div className="space-y-5">
      <datalist id={listId}>
        {champions.list.map((c) => (
          <option key={c.name} value={c.name} />
        ))}
      </datalist>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Coach inputs: {prefs.team}</h1>
          <p className="text-muted">
            What the data can't see. Saved in this browser only; the recommendations use it immediately.
          </p>
        </div>
        <div className="flex gap-2 text-sm">
          <button
            type="button"
            onClick={() => download('preferences.json', JSON.stringify(prefs, null, 2), 'application/json')}
            className="min-h-9 cursor-pointer rounded-md border border-line px-3"
          >
            Export
          </button>
          <button
            type="button"
            onClick={reset}
            className="min-h-9 cursor-pointer rounded-md border border-line px-3 text-muted"
          >
            Reset to the team file
          </button>
        </div>
      </header>
      <Section title="How much the recommendations follow you" hint="0 = data only, 1 = coach input dominates">
        <label className="flex items-center gap-3 text-sm">
          <input
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={prefs.weight ?? 0.5}
            onChange={(e) => setPrefs({ ...prefs, weight: Number(e.target.value) })}
            className="w-64"
          />
          <span className="tabular">{(prefs.weight ?? 0.5).toFixed(1)}</span>
        </label>
        <fieldset className="mt-3 flex flex-wrap gap-3 text-sm">
          <legend className="mb-1 text-xs text-muted">Team style</legend>
          {STYLES.map((s) => (
            <label key={s} className="flex items-center gap-1 capitalize">
              <input
                type="checkbox"
                checked={(strategy.style_tags ?? []).includes(s)}
                onChange={(e) =>
                  setStrategy({
                    style_tags: e.target.checked
                      ? [...(strategy.style_tags ?? []), s]
                      : (strategy.style_tags ?? []).filter((x) => x !== s),
                  })
                }
              />
              {s}
            </label>
          ))}
        </fieldset>
      </Section>
      <div className="grid gap-4 lg:grid-cols-2">
        {prefs.players.map((p, i) => (
          <PlayerEditor
            key={p.name}
            player={p}
            listId={listId}
            known={champions.byName}
            onChange={(next) => setPrefs({ ...prefs, players: prefs.players.map((x, j) => (j === i ? next : x)) })}
          />
        ))}
      </div>
      <Section title="Series strategy">
        <div className="grid gap-4 sm:grid-cols-2">
          <ChampionList
            label="Save for game 3+ (Fearless)"
            values={strategy.save_for_late_games ?? []}
            onChange={(v) => setStrategy({ save_for_late_games: v })}
            listId={listId}
            known={champions.byName}
          />
          <ChampionList
            label="Never pick"
            values={strategy.never_pick ?? []}
            onChange={(v) => setStrategy({ never_pick: v })}
            listId={listId}
            known={champions.byName}
          />
        </div>
        <div className="mt-4 space-y-2 text-sm">
          <p className="text-xs text-muted">Must-ban against a specific opponent</p>
          {Object.entries(mustBan).map(([team, champs]) => (
            <ChampionList
              key={team}
              label={team}
              values={champs}
              onChange={(v) => setStrategy({ must_ban_vs_opponent: { ...mustBan, [team]: v } })}
              listId={listId}
              known={champions.byName}
            />
          ))}
          <div className="flex gap-2">
            <input
              aria-label="Opponent team name"
              value={opponent}
              onChange={(e) => setOpponent(e.target.value)}
              placeholder="team name"
              className="min-h-8 rounded border border-line bg-bg px-2"
            />
            <button
              type="button"
              disabled={!opponent || opponent in mustBan}
              onClick={() => {
                setStrategy({ must_ban_vs_opponent: { ...mustBan, [opponent]: [] } })
                setOpponent('')
              }}
              className="min-h-8 cursor-pointer rounded border border-line px-2 disabled:opacity-40"
            >
              Add opponent
            </button>
          </div>
        </div>
      </Section>
    </div>
  )
}
