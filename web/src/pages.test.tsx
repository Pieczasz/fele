import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, test as it, vi } from 'vitest'
import { App } from './App.tsx'
import type { Coverage, Macro, Players, Team } from './api/client.ts'

// smoke tests for the report pages that the flow tests don't reach: each renders its data with the evidence (n)

const TEAM: Team = {
  team_id: 't1',
  name: 'Team One',
  league: 'LCS',
  games: 12,
  wins: 7,
  series: 5,
  first_game: '2026-01-01T00:00:00Z',
  last_game: '2026-09-01T00:00:00Z',
}
const PLAYERS: Players = {
  team: TEAM,
  players: [
    {
      player_id: 'p1',
      name: 'Midlaner',
      role: 'mid',
      current: true,
      last_game: '2026-09-01T00:00:00Z',
      n: 12,
      unique_champions: 6,
      effective_pool: 4.2,
      effective_pool_lo: 3.1,
      effective_pool_hi: 5.0,
      depth: 3,
      meta_overlap: { k: 2, n: 10, rate: 0.2, lo: 0.05, hi: 0.5 },
      champions: [
        {
          k: 3,
          n: 4,
          rate: 0.75,
          lo: 0.3,
          hi: 0.95,
          champion: 'Azir',
          key: 'Azir',
          shrunk: 0.6,
          shrunk_lo: 0.45,
          shrunk_hi: 0.72,
          recent_games: 2.5,
          comfort: 3,
          last_played: '2026-08-30T00:00:00Z',
        },
      ],
    },
  ],
}
const MACRO: Macro = {
  team: TEAM,
  period: 'recent',
  games: 12,
  rates: [
    {
      k: 9,
      n: 12,
      rate: 0.75,
      lo: 0.47,
      hi: 0.91,
      metric: 'got_first_drake',
      split: 'all',
      base_rate: 0.5,
      tendency: 'weak',
    },
  ],
  timings: [{ metric: 'drake_s', n: 9, median_s: 330, q25_s: 300, q75_s: 400 }],
  early_kills: [{ side: 'blue', kind: 'kill', cx: 2, cy: 3, count: 4 }],
  games_by_side: { blue: 6, red: 6 },
}
const COVERAGE: Coverage = {
  leagues: [{ league: 'LCS', teams: 1, games: 12, first_game: TEAM.first_game, last_game: TEAM.last_game }],
  soloq: [{ patch: '16.23', matches: 1500 }],
  teams: [TEAM],
}
const ROUTES: Record<string, unknown> = {
  '/teams': [TEAM],
  '/info': { ddragon_version: '16.23.1', live_patch: '16.23', demo_protected: false },
  '/teams/t1/players': PLAYERS,
  '/teams/t1/macro': MACRO,
  '/coverage': COVERAGE,
}

function renderAt(path: string) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const route = url.replace('/api', '').split('?')[0] ?? ''
      return Promise.resolve(Response.json(ROUTES[route] ?? {}))
    }),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('players page: pool size with its interval and champions with their games', async () => {
  renderAt('/teams/t1/players')
  expect(await screen.findByRole('heading', { name: 'Midlaner mid' })).toBeInTheDocument()
  expect(screen.getByText('4.2')).toBeInTheDocument()
  expect(screen.getByText('Azir')).toBeInTheDocument()
})

it('macro page: habits against the league, objective timings, side switch', async () => {
  renderAt('/teams/t1/macro')
  expect(await screen.findByText('Takes the first drake')).toBeInTheDocument()
  expect(screen.getByText('First drake')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Blue' }))
  expect(screen.queryByText('Takes the first drake')).not.toBeInTheDocument() // no blue-side rows in this fixture
})

it('coverage page: games per league and the solo-queue sample', async () => {
  renderAt('/coverage')
  expect(await screen.findByRole('heading', { name: 'Data coverage' })).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: 'Pro games by league' })).toBeInTheDocument() // data loaded
  expect(screen.getByText('Patch 16.23')).toBeInTheDocument()
})
