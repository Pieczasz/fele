import { RIOT_BOILERPLATE } from '../legal.ts'

export function Footer() {
  return (
    <footer className="mt-auto border-t border-slate-200 px-6 py-4 text-xs text-slate-500 dark:border-slate-800">
      <p>{RIOT_BOILERPLATE}</p>
      <p className="mt-1">Pro match data provided by GRID for the Sky's The Limit 2026 hackathon.</p>
    </footer>
  )
}
