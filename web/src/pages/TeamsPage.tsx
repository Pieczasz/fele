import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { api, type Team } from '../api/client.ts'
import { NBadge } from '../components/Evidence.tsx'
import { QueryState } from '../components/QueryState.tsx'
import { shortDate } from '../format.ts'

function byLeague(teams: Team[]): [string, Team[]][] {
  const groups = new Map<string, Team[]>()
  for (const t of teams) {
    groups.set(t.league, [...(groups.get(t.league) ?? []), t])
  }
  return [...groups.entries()]
}

const STEPS = [
  ['1', 'Pick an opponent', 'Their draft priorities by game number, player pools and habits, each with its n.'],
  ['2', 'Plan the series', 'Bo3 or Bo5 under Fearless: locks, what is left, what to save, series odds.'],
  ['3', 'Rehearse the draft', 'Pro draft order, five options with reasons on our turn, their likely answer.'],
] as const

/** Shown only when the API watches the League client (fele serve --lcu) and the client is open. */
function LiveStatus() {
  const live = useQuery({ queryKey: ['live'], queryFn: api.live, retry: false, refetchInterval: 5000 })
  if (!live.data?.connected) {
    return null
  }
  return (
    <p className="rounded-md border border-accent px-3 py-2 text-sm">
      League client connected{live.data.me ? ` as ${live.data.me}` : ''}.{' '}
      <Link to="/live" className="font-medium text-primary underline">
        Open fele Live
      </Link>{' '}
      for champ select help in your own games.
    </p>
  )
}

export function TeamsPage() {
  const teams = useQuery({ queryKey: ['teams'], queryFn: api.teams })
  const [query, setQuery] = useState('')
  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <h1 className="text-2xl font-bold">Draft prep for a Fearless series</h1>
        <ol className="grid gap-3 sm:grid-cols-3">
          {STEPS.map(([n, title, text]) => (
            <li key={n} className="rounded-lg border border-line bg-surface p-3">
              <p className="font-semibold">
                <span className="mr-2 inline-flex size-6 items-center justify-center rounded-full bg-primary-soft text-sm">
                  {n}
                </span>
                {title}
              </p>
              <p className="mt-1 text-sm text-muted">{text}</p>
            </li>
          ))}
        </ol>
        <LiveStatus />
      </header>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-lg font-semibold">Pick an opponent</h2>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted">Find a team</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="min-h-9 w-48 rounded-md border border-line bg-surface px-2"
          />
        </label>
      </div>
      <QueryState query={teams}>
        {(data) => (
          <div className="grid gap-5 md:grid-cols-2">
            {byLeague(data.filter((t) => t.name.toLowerCase().includes(query.trim().toLowerCase()))).map(
              ([league, list]) => (
                <section key={league} className="rounded-lg border border-line bg-surface p-4">
                  <h2 className="mb-2 font-semibold">{league}</h2>
                  <ul className="divide-y divide-line">
                    {list.map((t) => (
                      <li key={t.team_id}>
                        <Link
                          to={`/teams/${t.team_id}/scouting`}
                          className="flex min-h-11 items-center justify-between gap-3 rounded px-2 hover:bg-surface-2"
                        >
                          <span className="font-medium">{t.name}</span>
                          <span className="flex items-center gap-2 text-xs text-muted">
                            last {shortDate(t.last_game)} <NBadge n={t.games} />
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              ),
            )}
          </div>
        )}
      </QueryState>
    </div>
  )
}
