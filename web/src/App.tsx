import { useQuery } from '@tanstack/react-query'
import { NavLink, Route, Routes } from 'react-router'
import { api } from './api/client.ts'
import { Footer } from './components/Footer.tsx'

const navClass = ({ isActive }: { isActive: boolean }) => (isActive ? 'font-semibold' : 'text-slate-500')

function Status() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  let healthText = 'checking…'
  if (health.isError) {
    healthText = `unreachable (${health.error.message})`
  } else if (health.isSuccess) {
    healthText = health.data.status
  }
  const prefs = useQuery({ queryKey: ['preferences'], queryFn: api.preferences })
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">Engine status</h2>
      <p data-testid="health">API: {healthText}</p>
      {prefs.data ? (
        <div>
          <h3 className="font-medium">{prefs.data.team} — coach preferences</h3>
          <ul className="mt-2 grid gap-2 sm:grid-cols-5">
            {prefs.data.players.map((p) => (
              <li key={p.name} className="rounded border border-slate-200 p-2 text-sm dark:border-slate-800">
                <span className="font-medium">{p.name}</span> <span className="text-slate-500">{p.role}</span>
                <ul className="mt-1 text-xs">
                  {(p.pool ?? []).map((c) => (
                    <li key={c.champion}>
                      {c.champion} · {c.comfort}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  )
}

const Placeholder = ({ title }: { title: string }) => (
  <section>
    <h2 className="text-lg font-semibold">{title}</h2>
    <p className="text-slate-500">Coming in a later phase.</p>
  </section>
)

const NAV = [
  ['/', 'Status'],
  ['/scouting', 'Scouting'],
  ['/meta', 'Meta'],
  ['/planner', 'Series planner'],
  ['/draft', 'Mock draft'],
] as const

export function App() {
  return (
    <div className="flex min-h-screen flex-col bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="flex items-center gap-6 border-b border-slate-200 px-6 py-3 dark:border-slate-800">
        <h1 className="font-bold">fele</h1>
        <nav className="flex gap-4 text-sm">
          {NAV.map(([to, label]) => (
            <NavLink key={to} to={to} className={navClass}>
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-6">
        <Routes>
          <Route path="/" element={<Status />} />
          <Route path="/scouting" element={<Placeholder title="Opponent scouting" />} />
          <Route path="/meta" element={<Placeholder title="Meta & patch" />} />
          <Route path="/planner" element={<Placeholder title="Fearless series planner" />} />
          <Route path="/draft" element={<Placeholder title="Mock draft" />} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}
