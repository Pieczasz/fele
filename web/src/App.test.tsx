import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, test as it, vi } from 'vitest'
import { App } from './App.tsx'
import type { Meta, Scouting, Team } from './api/client.ts'
import { RIOT_BOILERPLATE } from './legal.ts'

const TEAM: Team = {
  team_id: 't1',
  name: 'Team One',
  league: 'LCS',
  games: 10,
  wins: 6,
  series: 4,
  first_game: '2026-01-01T00:00:00Z',
  last_game: '2026-09-01T00:00:00Z',
}
const rate = { k: 3, n: 10, rate: 0.3, lo: 0.1, hi: 0.6 }
const SCOUTING: Scouting = {
  team: TEAM,
  period: 'recent',
  games: 10,
  draft: [
    {
      ...rate,
      champion: 'Wukong',
      key: 'MonkeyKing',
      split_type: 'all',
      split: 'all',
      picks: 2,
      bans: 1,
      base_rate: 0.1,
      first_rotation: { ...rate, k: 2, rate: 0.2 },
      avg_slot: 5,
      tendency: 'weak',
    },
    {
      ...rate,
      k: 1,
      n: 4,
      champion: 'Azir',
      key: 'Azir',
      split_type: 'side',
      split: 'blue',
      picks: 1,
      bans: 0,
      base_rate: 0.2,
      first_rotation: { ...rate, k: 0, rate: 0 },
      avg_slot: 9,
      tendency: 'noise',
    },
  ],
  targeted_players: [{ ...rate, k: 2, n: 5, player: 'Mid', role: 'mid', champions: [] }],
}
const META: Meta = {
  window: 'live',
  windows: ['16.17', 'live'],
  patches: ['16.17'],
  live_patch: '16.23',
  rows: [
    {
      champion: 'MonkeyKing',
      name: 'Wukong',
      roles: ['jungle'],
      presence: { k: 4, n: 10, rate: 0.4, lo: 0.2, hi: 0.6 },
      picks: 3,
      bans: 1,
      pro_n: 3,
      pro_wr: 0.52,
      pro_wr_lo: 0.4,
      pro_wr_hi: 0.6,
      soloq_n: 100,
      soloq_wr: 0.51,
      soloq_wr_lo: 0.45,
      soloq_wr_hi: 0.57,
      delta: 0.02,
      meta_score: 1.2,
    },
  ],
}
const TEAM_LINK = /Team One/
const INFO = { ddragon_version: '16.23.1', live_patch: '16.23', demo_protected: false }

const DEFAULTS: Record<string, unknown> = { '/champions': [], '/teams/t1/cards': [] }

function fakeApi(routes: Record<string, unknown>, status = 200) {
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      const path = url.replace('/api', '').split('?')[0] ?? ''
      calls.push(`${init?.method ?? 'GET'} ${path}`)
      if (status !== 200 && path !== '/info') {
        return Promise.resolve(Response.json({ detail: 'Login required' }, { status }))
      }
      return Promise.resolve(Response.json(routes[path] ?? DEFAULTS[path] ?? {}))
    }),
  )
  return calls
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

it('lists teams by league and shows the Riot boilerplate', async () => {
  fakeApi({ '/teams': [TEAM], '/info': INFO })
  renderAt('/')
  expect(await screen.findByRole('link', { name: TEAM_LINK })).toHaveAttribute('href', '/teams/t1/scouting')
  expect(screen.getByRole('heading', { name: 'LCS' })).toBeInTheDocument()
  expect(screen.getByText(RIOT_BOILERPLATE)).toBeInTheDocument()
})

it('shows draft priorities with their evidence and switches splits', async () => {
  fakeApi({ '/teams': [TEAM], '/info': INFO, '/teams/t1/scouting': SCOUTING })
  renderAt('/teams/t1/scouting')
  const row = (await screen.findByRole('rowheader', { name: 'Wukong' })).closest('tr') as HTMLElement
  expect(within(row).getByText('3 of 10 games')).toBeInTheDocument() // the n behind the 30%
  expect(within(row).getByText('Weak')).toBeInTheDocument()
  expect(screen.getByText('Mid')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Blue side' }))
  expect(await screen.findByRole('rowheader', { name: 'Azir' })).toBeInTheDocument()
  expect(screen.queryByRole('rowheader', { name: 'Wukong' })).not.toBeInTheDocument()
})

it('asks for the demo password when the API says so', async () => {
  const calls = fakeApi({ '/info': { ...INFO, demo_protected: true } }, 401)
  renderAt('/')
  const input = await screen.findByLabelText('Password')
  fireEvent.change(input, { target: { value: 'nope' } })
  fireEvent.click(screen.getByRole('button', { name: 'Open the demo' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Wrong password')
  expect(calls).toContain('POST /login')
})

it('ranks the live meta with sample sizes', async () => {
  fakeApi({ '/teams': [TEAM], '/info': INFO, '/meta': META })
  renderAt('/meta')
  expect(await screen.findByRole('heading', { name: 'Live meta (patch 16.23)' })).toBeInTheDocument()
  const row = screen.getByRole('rowheader', { name: 'Wukong' }).closest('tr') as HTMLElement
  expect(within(row).getByText('1.20')).toBeInTheDocument()
  expect(within(row).getByText('4 of 10 games')).toBeInTheDocument()
})
