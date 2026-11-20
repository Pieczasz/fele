import { useQuery } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { Link, Navigate, NavLink, Route, Routes } from 'react-router'
import { api, LoginRequiredError } from './api/client.ts'
import { Footer } from './components/Footer.tsx'
import { Login } from './components/Login.tsx'
import { CoachPage } from './pages/CoachPage.tsx'
import { CoveragePage } from './pages/CoveragePage.tsx'
import { DraftPage } from './pages/DraftPage.tsx'
import { MacroPage } from './pages/MacroPage.tsx'
import { MetaPage } from './pages/MetaPage.tsx'
import { PlannerPage } from './pages/PlannerPage.tsx'
import { PlayersPage } from './pages/PlayersPage.tsx'
import { ScoutingPage } from './pages/ScoutingPage.tsx'
import { TeamLayout } from './pages/TeamLayout.tsx'
import { TeamsPage } from './pages/TeamsPage.tsx'
import { applyTheme, initialTheme, type Theme } from './theme.ts'

const NAV = [
  ['/', 'Teams'],
  ['/planner', 'Series plan'],
  ['/draft', 'Mock draft'],
  ['/meta', 'Meta'],
  ['/coach', 'Coach'],
  ['/coverage', 'Data'],
] as const

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme)
  return (
    <button
      type="button"
      aria-pressed={theme === 'dark'}
      onClick={() => {
        const next: Theme = theme === 'dark' ? 'light' : 'dark'
        applyTheme(next, true)
        setTheme(next)
      }}
      className="min-h-9 cursor-pointer rounded-md border border-line px-3 text-sm text-muted hover:text-ink"
    >
      Dark theme
    </button>
  )
}

export function App() {
  const teams = useQuery({ queryKey: ['teams'], queryFn: api.teams, retry: false })
  const needsLogin = teams.error instanceof LoginRequiredError
  const mainId = useId()
  return (
    <div className="flex min-h-screen flex-col bg-bg text-ink">
      <a href={`#${mainId}`} className="sr-only focus:not-sr-only focus:absolute focus:p-2">
        Skip to content
      </a>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <Link to="/" className="text-lg font-bold tracking-tight">
            fele <span className="text-sm font-normal text-muted">Fearless Ledger</span>
          </Link>
          <nav aria-label="Main" className="flex gap-1 text-sm">
            {NAV.map(([to, label]) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 ${isActive ? 'bg-primary-soft font-semibold text-ink' : 'text-muted hover:text-ink'}`
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main id={mainId} className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
        {needsLogin ? (
          <Login />
        ) : (
          <Routes>
            <Route path="/" element={<TeamsPage />} />
            <Route path="/teams/:teamId" element={<TeamLayout />}>
              <Route index={true} element={<Navigate to="scouting" replace={true} />} />
              <Route path="scouting" element={<ScoutingPage />} />
              <Route path="players" element={<PlayersPage />} />
              <Route path="macro" element={<MacroPage />} />
            </Route>
            <Route path="/planner" element={<PlannerPage />} />
            <Route path="/draft" element={<DraftPage />} />
            <Route path="/coach" element={<CoachPage />} />
            <Route path="/meta" element={<MetaPage />} />
            <Route path="/coverage" element={<CoveragePage />} />
            <Route path="*" element={<p className="text-muted">Page not found.</p>} />
          </Routes>
        )}
      </main>
      <Footer />
    </div>
  )
}
