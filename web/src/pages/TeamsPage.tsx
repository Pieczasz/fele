import { useQuery } from '@tanstack/react-query'
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

export function TeamsPage() {
  const teams = useQuery({ queryKey: ['teams'], queryFn: api.teams })
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">Pick an opponent</h1>
        <p className="text-muted">
          Draft priorities, player pools and macro habits from pro games. Every number shows how many games it rests on.
        </p>
      </header>
      <QueryState query={teams}>
        {(data) => (
          <div className="grid gap-5 md:grid-cols-2">
            {byLeague(data).map(([league, list]) => (
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
            ))}
          </div>
        )}
      </QueryState>
    </div>
  )
}
