import { useQuery } from '@tanstack/react-query'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { api } from '../api/client.ts'
import { Segmented } from '../components/Segmented.tsx'
import { shortDate } from '../format.ts'
import { EMPTY_PLAN, usePeriod, usePlan, useTeamId } from '../hooks.ts'

const TABS = [
  ['scouting', 'Draft tendencies'],
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
  const [plan, setPlan] = usePlan()
  const navigate = useNavigate()
  const usesPeriod = !useLocation().pathname.endsWith('/players') // the players page always shows current pools
  const team = useQuery({ queryKey: ['teams'], queryFn: api.teams }).data?.find((t) => t.team_id === teamId)
  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-muted">{team ? `${team.league} · scouting report` : 'Scouting report'}</p>
          <h1 className="text-2xl font-bold">{team?.name ?? 'Unknown team'}</h1>
          {team ? (
            <p className="tabular text-sm text-muted">
              {team.wins}–{team.games - team.wins} in {team.games} games ({team.series} series) ·{' '}
              {shortDate(team.first_game)} – {shortDate(team.last_game)}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {usesPeriod ? <Segmented label="Period" options={PERIODS} value={period} onChange={setPeriod} /> : null}
          <button
            type="button"
            onClick={() => {
              // same opponent: keep the plan; another one: replace it, after a confirm if it has games or saves
              if (plan.opponent !== teamId) {
                const inProgress = plan.games.length > 0 || Object.keys(plan.save).length > 0
                if (inProgress && !globalThis.confirm('Replace the current series plan (its games and save list)?')) {
                  return
                }
                setPlan({ ...EMPTY_PLAN, opponent: teamId })
              }
              navigate('/planner')
            }}
            className="min-h-9 cursor-pointer rounded-md bg-primary px-3 text-sm font-medium text-bg"
          >
            Plan a series vs this team
          </button>
        </div>
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
