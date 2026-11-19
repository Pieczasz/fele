import { useQuery } from '@tanstack/react-query'
import { api, type Player } from '../api/client.ts'
import { Champion } from '../components/ChampionIcon.tsx'
import { NBadge } from '../components/Evidence.tsx'
import { QueryState } from '../components/QueryState.tsx'
import { interval, pct, shortDate } from '../format.ts'
import { useTeamId } from '../hooks.ts'

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div title={hint}>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="tabular font-semibold">{value}</dd>
    </div>
  )
}

function PlayerCard({ p }: { p: Player }) {
  return (
    <article className="rounded-lg border border-line bg-surface p-4">
      <header className="mb-3 flex items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">
          {p.name} <span className="text-sm font-normal capitalize text-muted">{p.role}</span>
        </h2>
        <span className="flex items-center gap-2 text-xs text-muted">
          last {shortDate(p.last_game)} <NBadge n={p.n} unit="pro games" />
        </span>
      </header>
      <dl className="mb-3 grid grid-cols-3 gap-3">
        <Stat
          label="Pool size"
          value={`${p.effective_pool.toFixed(1)}`}
          hint={`Effective pool (equally played champions), 95% ${p.effective_pool_lo.toFixed(1)}–${p.effective_pool_hi.toFixed(1)}; ${p.unique_champions} different champions`}
        />
        <Stat
          label="Depth"
          value={`${p.depth}`}
          hint="Champions with at least one recency-weighted game (90-day half-life)"
        />
        <Stat
          label="Live meta"
          value={`${p.meta_overlap.k}/${p.meta_overlap.n}`}
          hint="Top live meta champions for the role with 2+ pro games"
        />
      </dl>
      <table className="w-full text-sm">
        <caption className="sr-only">{p.name}'s most comfortable champions</caption>
        <thead className="text-left text-xs text-muted">
          <tr>
            <th scope="col" className="py-1 font-medium">
              Champion
            </th>
            <th scope="col" className="text-right font-medium">
              Record
            </th>
            <th
              scope="col"
              className="text-right font-medium"
              title="Win rate pulled toward the role average when games are few"
            >
              Adj. win rate
            </th>
            <th scope="col" className="text-right font-medium" title="Last played">
              Last
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {p.champions.map((c) => (
            <tr key={c.champion}>
              <th scope="row" className="py-1 text-left font-normal">
                <Champion name={c.champion} championKey={c.key} />
              </th>
              <td className="text-right">
                <NBadge k={c.k} n={c.n} unit="games won" />
              </td>
              <td className="tabular text-right" title={`95% ${interval(c.shrunk_lo, c.shrunk_hi)}`}>
                {pct(c.shrunk)}
              </td>
              <td className="tabular text-right text-muted">{shortDate(c.last_played)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  )
}

export function PlayersPage() {
  const teamId = useTeamId()
  const query = useQuery({ queryKey: ['players', teamId], queryFn: () => api.players(teamId) })
  return (
    <QueryState query={query}>
      {(data) => {
        const current = data.players.filter((p) => p.current)
        const former = data.players.filter((p) => !p.current)
        return (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              Current lineup: players in the team's latest games. Champions are ranked by comfort: recent games,
              weighted by how well they went. Uses all periods (player pools need more than 120 days of games).
            </p>
            <div className="grid gap-4 lg:grid-cols-2">
              {current.map((p) => (
                <PlayerCard key={p.player_id} p={p} />
              ))}
            </div>
            {former.length > 0 ? (
              <details className="rounded-lg border border-line bg-surface p-4">
                <summary className="cursor-pointer font-medium">
                  Earlier players ({former.length}) — last game for this team before its latest games
                </summary>
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  {former.map((p) => (
                    <PlayerCard key={p.player_id} p={p} />
                  ))}
                </div>
              </details>
            ) : null}
          </div>
        )
      }}
    </QueryState>
  )
}
