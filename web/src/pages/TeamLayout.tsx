import { useQuery } from '@tanstack/react-query'
import { NavLink, Outlet } from 'react-router'
import { api } from '../api/client.ts'
import { Segmented } from '../components/Segmented.tsx'
import { shortDate } from '../format.ts'
import { usePeriod, useTeamId } from '../hooks.ts'

const TABS = [
  ['scouting', 'Draft'],
  ['players', 'Players'],
  ['macro', 'Macro'],
] as const

const PERIODS = [
  ['recent', 'Last 120 days'],
  ['all', 'All games'],
] as const

export function TeamLayout() {
  const teamId = useTeamId()
  const [period, setPeriod] = usePeriod()
  const team = useQuery({ queryKey: ['teams'], queryFn: api.teams }).data?.find((t) => t.team_id === teamId)
  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted">{team ? `${team.league} · scouting report` : 'Scouting report'}</p>
          <h1 className="text-2xl font-bold">{team?.name ?? teamId}</h1>
          {team ? (
            <p className="tabular text-sm text-muted">
              {team.wins}–{team.games - team.wins} in {team.games} games ({team.series} series) ·{' '}
              {shortDate(team.first_game)} – {shortDate(team.last_game)}
            </p>
          ) : null}
        </div>
        <Segmented label="Period" options={PERIODS} value={period} onChange={setPeriod} />
      </header>
      <nav aria-label="Report sections" className="flex gap-1 border-b border-line">
        {TABS.map(([to, label]) => (
          <NavLink
            key={to}
            to={{ pathname: to, search: `?period=${period}` }}
            className={({ isActive }) =>
              `-mb-px border-b-2 px-3 py-2 text-sm ${isActive ? 'border-primary font-semibold text-ink' : 'border-transparent text-muted hover:text-ink'}`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  )
}
