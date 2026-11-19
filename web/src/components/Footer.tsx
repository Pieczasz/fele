import { RIOT_BOILERPLATE } from '../legal.ts'

export function Footer() {
  return (
    <footer className="mt-auto border-t border-line px-6 py-4 text-xs text-muted">
      <p>{RIOT_BOILERPLATE}</p>
      <p className="mt-1">
        Pro match data provided by GRID for the Sky's The Limit 2026 hackathon. Champion and map images: Riot Games Data
        Dragon. Solo-queue sample: Riot Games API.
      </p>
    </footer>
  )
}
