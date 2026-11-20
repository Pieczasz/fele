import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, test as it, vi } from 'vitest'
import { App } from './App.tsx'
import type { DraftAdvice, Preferences } from './api/client.ts'
import { actor, kind, split } from './draftOrder.ts'

const TEAM = {
  team_id: 'fq',
  name: 'FlyQuest',
  league: 'LCS',
  games: 10,
  wins: 6,
  series: 4,
  first_game: '2026-01-01T00:00:00Z',
  last_game: '2026-09-01T00:00:00Z',
}
const PREFS: Preferences = {
  team: 'Cloud9 Kia',
  weight: 0.5,
  players: [
    { name: 'Blaber', role: 'jungle', wants_prio: false, pool: [{ champion: 'Vi', comfort: 'signature', note: '' }] },
  ],
  strategy: { save_for_late_games: [], must_ban_vs_opponent: {}, never_pick: [], style_tags: [] },
}
const CHAMPS = ['Ahri', 'Azir', 'Vi', 'Jinx', 'Nocturne'].map((name) => ({ name, key: name, roles: ['mid'] }))
const comp = {
  champions: [],
  ap_share: 0.5,
  damage: 'mixed',
  totals: {},
  scaling: 'mid',
  warnings: [],
  contribution: {},
}
const ADVICE: DraftAdvice = {
  next: { slot: 1, who: 'us', kind: 'ban', phase: 'ban1' },
  options: [
    {
      champion: 'Nocturne',
      key: 'Nocturne',
      role: null,
      score: -2,
      parts: {},
      reasons: ['they pick it 17% of the time at their next pick (model)'],
      win_prob: null,
    },
  ],
  likely: [],
  win_prob: { mean: 0.6, p10: 0.58, p90: 0.62, note: 'Elo-dominated' },
  our_comp: comp,
  their_comp: comp,
}

function fakeApi() {
  const calls: { path: string; body?: unknown }[] = []
  const routes: Record<string, unknown> = {
    '/teams': [TEAM],
    '/info': { ddragon_version: '16.23.1', live_patch: '16.23', demo_protected: false },
    '/preferences': PREFS,
    '/champions': CHAMPS,
    '/draft/recommend': ADVICE,
    '/teams/fq/players': { team: TEAM, players: [] },
  }
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      const path = url.replace('/api', '').split('?')[0] ?? ''
      calls.push({ path, body: init?.body ? JSON.parse(String(init.body)) : undefined })
      return Promise.resolve(Response.json(routes[path] ?? {}))
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

beforeEach(() => {
  localStorage.clear()
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('draft order', () => {
  it('follows the pro template for both first-pick cases', () => {
    expect([0, 1, 6, 7, 8, 9].map((i) => actor(i, true))).toEqual(['us', 'them', 'us', 'them', 'them', 'us'])
    expect(actor(6, false)).toBe('them')
    expect([kind(0), kind(6), kind(12), kind(16)]).toEqual(['ban', 'pick', 'ban', 'pick'])
    const s = split(['A', 'B', 'C', 'D', 'E', 'F', 'Ahri', 'Vi'], true)
    expect(s.us).toEqual({ ban: ['A', 'C', 'E'], pick: ['Ahri'] })
    expect(s.them.pick).toEqual(['Vi'])
  })
})

it('mock draft: shows options with reasons, applies a click and the 1 key', async () => {
  localStorage.setItem(
    'fele-plan',
    JSON.stringify({ opponent: 'fq', bestOf: 3, weStartBlue: true, games: [], save: {} }),
  )
  const calls = fakeApi()
  renderAt('/draft')
  expect(await screen.findByText('they pick it 17% of the time at their next pick (model)')).toBeInTheDocument()
  expect(screen.getByText('Our win probability 60%')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Ahri' }))
  await waitFor(() => expect(calls.at(-1)?.body).toMatchObject({ actions: ['Ahri'], them: 'fq' }))
  fireEvent.keyDown(globalThis.window, { key: '1' })
  await waitFor(() => expect(calls.at(-1)?.body).toMatchObject({ actions: ['Ahri', 'Nocturne'] }))
  expect(screen.getByRole('button', { name: 'Ahri' })).toBeDisabled() // taken this game
})

it('planner: shows Fearless locks and remaining pools from the saved plan', async () => {
  const game = { id: 'g1', ours: ['Vi', 'Ahri'], theirs: ['Azir'], bans: [], result: 'lost' }
  localStorage.setItem(
    'fele-plan',
    JSON.stringify({ opponent: 'fq', bestOf: 3, weStartBlue: true, games: [game], save: {} }),
  )
  fakeApi()
  renderAt('/planner')
  const locks = (await screen.findByRole('heading', { name: 'Fearless-locked' })).closest('section') as HTMLElement
  expect(within(locks).getByText('Azir')).toBeInTheDocument()
  expect(await screen.findByText('Score 0–1 · next: game 2')).toBeInTheDocument()
  const pools = screen.getByRole('heading', { name: 'Our remaining pools' }).closest('section') as HTMLElement
  expect(within(pools).getByText('0 of 1 champions left')).toBeInTheDocument() // Vi is locked
})

it('coach inputs are edited in this browser only', async () => {
  fakeApi()
  renderAt('/coach')
  const weight = await screen.findByRole('slider')
  fireEvent.change(weight, { target: { value: '0.8' } })
  await waitFor(() => expect(JSON.parse(localStorage.getItem('fele-prefs') ?? '{}').weight).toBe(0.8))
})
