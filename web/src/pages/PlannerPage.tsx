import { useMutation, useQuery } from '@tanstack/react-query'
import { type ChangeEvent, useId, useState } from 'react'
import { Link } from 'react-router'
import { api, type SeriesPlan, type SeriesRequest } from '../api/client.ts'
import { Champion } from '../components/ChampionIcon.tsx'
import { NBadge } from '../components/Evidence.tsx'
import { Section } from '../components/QueryState.tsx'
import { Segmented } from '../components/Segmented.tsx'
import { pct } from '../format.ts'
import {
  EMPTY_PLAN,
  lockedBy,
  type PlannedGame,
  type SeriesPlanState,
  useChampions,
  usePlan,
  usePrefs,
  weFirstNext,
} from '../hooks.ts'
import { download } from '../store.ts'

const BEST_OF = [
  ['3', 'Best of 3'],
  ['5', 'Best of 5'],
] as const
const COMFORT_POOL = new Set(['signature', 'comfortable'])

function toCsv(plan: SeriesPlanState): string {
  const rows = [['game', 'result', 'our picks', 'their picks', 'bans']]
  plan.games.forEach((g, i) => {
    rows.push([String(i + 1), g.result ?? '', g.ours.join('|'), g.theirs.join('|'), g.bans.join('|')])
  })
  rows.push([], ['save', 'from game'], ...Object.entries(plan.save).map(([c, game]) => [c, String(game)]))
  return rows.map((r) => r.map((v) => `"${v.replaceAll('"', '""')}"`).join(',')).join('\n')
}

function GameEditor({
  game,
  index,
  onChange,
  onRemove,
  champions,
}: {
  game: PlannedGame
  index: number
  onChange: (g: PlannedGame) => void
  onRemove: () => void
  champions: string[]
}) {
  const listId = useId()
  const edit = (team: 'ours' | 'theirs', slot: number, value: string) => {
    const next = [...game[team]]
    next[slot] = value
    onChange({ ...game, [team]: next.filter((v, i) => v || i < next.length - 1) })
  }
  return (
    <article className="rounded-lg border border-line bg-surface p-3">
      <header className="mb-2 flex items-center justify-between">
        <h3 className="font-semibold">Game {index + 1}</h3>
        <div className="flex items-center gap-2">
          <Segmented
            label={`Game ${index + 1} result`}
            options={
              [
                ['won', 'Won'],
                ['lost', 'Lost'],
              ] as const
            }
            value={game.result ?? 'won'}
            onChange={(result) => onChange({ ...game, result })}
          />
          <button
            type="button"
            onClick={onRemove}
            className="min-h-9 cursor-pointer rounded-md border border-line px-2 text-sm text-muted"
          >
            Remove
          </button>
        </div>
      </header>
      <datalist id={listId}>
        {champions.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      <div className="grid gap-3 sm:grid-cols-2">
        {(['ours', 'theirs'] as const).map((team) => (
          <fieldset key={team} className="space-y-1">
            <legend className="text-xs text-muted">{team === 'ours' ? 'Our picks' : 'Their picks'}</legend>
            {[0, 1, 2, 3, 4].map((slot) => (
              <input
                key={slot}
                list={listId}
                aria-label={`Game ${index + 1}, ${team === 'ours' ? 'our' : 'their'} pick ${slot + 1}`}
                value={game[team][slot] ?? ''}
                onChange={(e) => edit(team, slot, e.target.value)}
                className="min-h-8 w-full rounded border border-line bg-bg px-2 text-sm"
              />
            ))}
          </fieldset>
        ))}
      </div>
    </article>
  )
}

function Results({ data, keys }: { data: SeriesPlan; keys: string[] }) {
  const p = data.plan
  const columns = (p.availability[keys[0] ?? ''] ?? []).map((_, i) => `G${p.first_game + i}`)
  const diff = data.difference
  return (
    <div className="space-y-3">
      <p className="text-lg">
        Series win probability <strong>{pct(p.series_win)}</strong>{' '}
        <span className="text-sm text-muted">
          ± {pct(p.series_win_se, 1)} (Monte Carlo), ~{p.expected_games.toFixed(1)} games
        </span>
      </p>
      {diff === null || diff === undefined ? null : (
        <p className="text-sm">
          With the save list vs without: <strong>{signedPct(diff)}</strong> ± {pct(data.difference_se ?? 0, 1)}
          {data.within_noise ? ' (within noise: no measurable effect on series odds)' : ''}
        </p>
      )}
      <table className="w-full text-sm">
        <caption className="sr-only">Chance each champion is still available, by game</caption>
        <thead className="text-left text-xs text-muted">
          <tr>
            <th scope="col" className="font-medium">
              Champion
            </th>
            {columns.map((label) => (
              <th key={label} scope="col" className="text-right font-medium">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {keys.map((c) => (
            <tr key={c}>
              <th scope="row" className="py-1 text-left font-normal">
                {c}
              </th>
              {columns.map((label, i) => (
                <td key={label} className="text-right tabular">
                  {pct(p.availability[c]?.[i])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="text-xs text-muted">
        {p.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </div>
  )
}

function signedPct(x: number): string {
  return `${x >= 0 ? '+' : ''}${pct(x, 1)}`
}

export function PlannerPage() {
  const teams = useQuery({ queryKey: ['teams'], queryFn: api.teams })
  const champions = useChampions()
  const [prefs] = usePrefs()
  const [plan, setPlan] = usePlan()
  const [saveChamp, setSaveChamp] = useState('')
  const [saveGame, setSaveGame] = useState(3)
  const allChampionsId = useId()
  const locked = lockedBy(plan)
  const theirPlayers = useQuery({
    queryKey: ['players', plan.opponent],
    queryFn: () => api.players(plan.opponent),
    enabled: Boolean(plan.opponent),
  })
  const played = plan.games.filter((g) => g.result !== null)
  const wins = played.filter((g) => g.result === 'won').length
  const losses = played.length - wins
  const keys = [
    ...new Set([
      ...Object.keys(plan.save),
      ...(prefs?.players ?? []).flatMap((p) =>
        (p.pool ?? []).filter((c) => COMFORT_POOL.has(c.comfort ?? '')).map((c) => c.champion),
      ),
    ]),
  ].slice(0, 16)

  const simulate = useMutation({
    mutationFn: (branchLoss: boolean) => {
      const body: SeriesRequest = {
        us: prefs?.team ?? 'Cloud9 Kia',
        them: plan.opponent,
        best_of: plan.bestOf,
        we_start_blue: plan.weStartBlue,
        save: plan.save,
        sims: 200,
        start_game: plan.games.length + 1 + (branchLoss ? 1 : 0),
        wins,
        losses: losses + (branchLoss ? 1 : 0),
        locked: [...locked.keys()],
        we_first_next: branchLoss ? true : weFirstNext(plan),
        key_champions: keys,
        preferences: prefs,
      }
      return api.simulate(body)
    },
  })

  const importJson = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setPlan({ ...EMPTY_PLAN, ...(JSON.parse(await file.text()) as SeriesPlanState) })
    }
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Fearless series planner</h1>
          <p className="text-muted">
            Plan the whole series: every champion picked is gone for the rest of it, for both teams.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <button
            type="button"
            onClick={() => download('fele-series-plan.json', JSON.stringify(plan, null, 2), 'application/json')}
            className="min-h-9 cursor-pointer rounded-md border border-line px-3"
          >
            Export JSON
          </button>
          <button
            type="button"
            onClick={() => download('fele-series-plan.csv', toCsv(plan), 'text/csv')}
            className="min-h-9 cursor-pointer rounded-md border border-line px-3"
          >
            Export CSV
          </button>
          <label className="flex min-h-9 cursor-pointer items-center rounded-md border border-line px-3">
            Import JSON
            <input type="file" accept="application/json" onChange={importJson} className="sr-only" />
          </label>
          <button
            type="button"
            onClick={() => setPlan({ ...EMPTY_PLAN, opponent: plan.opponent })}
            className="min-h-9 cursor-pointer rounded-md border border-line px-3 text-muted"
          >
            New series
          </button>
        </div>
      </header>

      <Section title="Series">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm">
            <span className="mr-2 text-muted">Opponent</span>
            <select
              value={plan.opponent}
              onChange={(e) => setPlan({ ...plan, opponent: e.target.value })}
              className="min-h-9 rounded-md border border-line bg-surface px-2"
            >
              <option value="">Choose…</option>
              {(teams.data ?? []).map((t) => (
                <option key={t.team_id} value={t.team_id}>
                  {t.name} ({t.league})
                </option>
              ))}
            </select>
          </label>
          <Segmented
            label="Format"
            options={BEST_OF}
            value={String(plan.bestOf) as '3' | '5'}
            onChange={(v) => setPlan({ ...plan, bestOf: v === '5' ? 5 : 3 })}
          />
          <Segmented
            label="Game 1 side"
            options={
              [
                ['blue', 'G1: we are blue'],
                ['red', 'G1: we are red'],
              ] as const
            }
            value={plan.weStartBlue ? 'blue' : 'red'}
            onChange={(v) => setPlan({ ...plan, weStartBlue: v === 'blue' })}
          />
          <span className="text-sm text-muted">
            Score {wins}–{losses} · next: game {plan.games.length + 1}
          </span>
        </div>
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        {plan.games.map((g, i) => (
          <GameEditor
            key={g.id ?? `game-${i + 1}`}
            game={g}
            index={i}
            champions={champions.list.map((c) => c.name)}
            onChange={(next) => setPlan({ ...plan, games: plan.games.map((x, j) => (j === i ? next : x)) })}
            onRemove={() => setPlan({ ...plan, games: plan.games.filter((_, j) => j !== i) })}
          />
        ))}
        {plan.games.length < plan.bestOf ? (
          <div className="flex flex-col items-start gap-2 rounded-lg border border-dashed border-line p-4 text-sm">
            <p className="text-muted">Game {plan.games.length + 1}</p>
            <Link to="/draft" className="text-primary underline">
              Draft it on the mock draft board
            </Link>
            <button
              type="button"
              onClick={() =>
                setPlan({
                  ...plan,
                  games: [...plan.games, { id: crypto.randomUUID(), ours: [], theirs: [], bans: [], result: 'won' }],
                })
              }
              className="cursor-pointer text-primary underline"
            >
              …or enter its picks by hand
            </button>
          </div>
        ) : null}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Fearless-locked" hint={<NBadge n={locked.size} unit="champions" />}>
          {locked.size === 0 ? (
            <p className="text-muted">Nothing locked yet.</p>
          ) : (
            <ul className="flex flex-wrap gap-2 text-sm">
              {[...locked.entries()].map(([c, game]) => (
                <li key={c} className="flex items-center gap-1">
                  <Champion name={c} championKey={champions.byName.get(c)?.key ?? null} />
                  <span className="text-xs text-muted">G{game}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>
        <Section title="Save for later games" hint="Our side won't pick these before the given game">
          <div className="mb-2 flex flex-wrap gap-2 text-sm">
            <input
              list={allChampionsId}
              aria-label="Champion to save"
              value={saveChamp}
              onChange={(e) => setSaveChamp(e.target.value)}
              className="min-h-9 rounded-md border border-line bg-bg px-2"
            />
            <datalist id={allChampionsId}>
              {champions.list.map((c) => (
                <option key={c.name} value={c.name} />
              ))}
            </datalist>
            <label className="flex items-center gap-1">
              from game
              <input
                type="number"
                min={2}
                max={5}
                value={saveGame}
                onChange={(e) => setSaveGame(Number(e.target.value))}
                className="min-h-9 w-14 rounded-md border border-line bg-bg px-2"
              />
            </label>
            <button
              type="button"
              disabled={!champions.byName.has(saveChamp)}
              onClick={() => {
                setPlan({ ...plan, save: { ...plan.save, [saveChamp]: saveGame } })
                setSaveChamp('')
              }}
              className="min-h-9 cursor-pointer rounded-md border border-line px-3 disabled:opacity-40"
            >
              Save
            </button>
          </div>
          <ul className="space-y-1 text-sm">
            {Object.entries(plan.save).map(([c, game]) => (
              <li key={c} className="flex items-center justify-between">
                <span>
                  {c} <span className="text-muted">from game {game}</span>
                </span>
                <button
                  type="button"
                  onClick={() => {
                    const { [c]: _, ...rest } = plan.save
                    setPlan({ ...plan, save: rest })
                  }}
                  className="cursor-pointer text-xs text-muted underline"
                >
                  remove
                </button>
              </li>
            ))}
          </ul>
        </Section>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Our remaining pools" hint="comfortable and signature champions not yet locked">
          <ul className="space-y-1 text-sm">
            {(prefs?.players ?? []).map((p) => {
              const pool = (p.pool ?? []).filter((c) => COMFORT_POOL.has(c.comfort ?? ''))
              const left = pool.filter((c) => !locked.has(c.champion))
              return (
                <li key={p.name}>
                  <strong>{p.name}</strong> <span className="text-muted">{p.role}</span>:{' '}
                  {left.map((c) => c.champion).join(', ') || '—'}{' '}
                  <NBadge k={left.length} n={pool.length} unit="champions left" />
                </li>
              )
            })}
          </ul>
        </Section>
        <Section title="Their remaining pools" hint="most comfortable pro champions, not yet locked">
          <ul className="space-y-1 text-sm">
            {(theirPlayers.data?.players ?? [])
              .filter((p) => p.current)
              .map((p) => {
                const left = p.champions.filter((c) => !locked.has(c.champion))
                return (
                  <li key={p.player_id}>
                    <strong>{p.name}</strong> <span className="text-muted">{p.role}</span>:{' '}
                    {left
                      .slice(0, 5)
                      .map((c) => c.champion)
                      .join(', ') || '—'}{' '}
                    <NBadge k={left.length} n={p.champions.length} unit="top champions left" />
                  </li>
                )
              })}
          </ul>
        </Section>
      </div>

      <Section title="Simulate the rest of the series" hint="Monte Carlo with the draft model for both teams">
        <div className="mb-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!plan.opponent || simulate.isPending}
            onClick={() => simulate.mutate(false)}
            className="min-h-9 cursor-pointer rounded-md bg-primary px-3 text-sm font-medium text-bg disabled:opacity-40"
          >
            Simulate from here
          </button>
          <button
            type="button"
            disabled={!plan.opponent || simulate.isPending}
            onClick={() => simulate.mutate(true)}
            className="min-h-9 cursor-pointer rounded-md border border-primary px-3 text-sm disabled:opacity-40"
          >
            What if we lose the next game?
          </button>
        </div>
        {simulate.isPending ? (
          <p role="status" className="text-muted">
            Simulating 200 series…
          </p>
        ) : null}
        {simulate.isError ? (
          <p role="alert" className="text-bad">
            {simulate.error.message}
          </p>
        ) : null}
        {simulate.variables === true && simulate.data ? (
          <p className="mb-2 text-xs text-muted">
            Branch: we lose game {plan.games.length + 1}. Its picks are unknown, so only the locks so far are applied.
          </p>
        ) : null}
        {simulate.data ? <Results data={simulate.data} keys={keys} /> : null}
      </Section>
    </div>
  )
}
