import type { Page, Route } from '@playwright/test'
import { actor, kind, TEMPLATE } from '../src/draftOrder.ts'

/** A small, consistent fake API for browser tests: one opponent, 24 champions, a draft endpoint that answers for
 * whatever slot the board is on, and a League client in champ select. */

export const real = process.env.E2E_REAL === '1'

const TEAM = {
  team_id: 'fq',
  name: 'FlyQuest',
  league: 'LCS',
  games: 12,
  wins: 7,
  series: 5,
  first_game: '2026-01-01T00:00:00Z',
  last_game: '2026-09-01T00:00:00Z',
}
const NAMES = [
  'Ahri',
  'Azir',
  'Vi',
  'Jinx',
  'Nocturne',
  'Orianna',
  'Lee Sin',
  'Viego',
  "Kai'Sa",
  'Thresh',
  'Rakan',
  'Nautilus',
  'Gnar',
  'Renekton',
  'Rumble',
  'Sejuani',
  'Xin Zhao',
  'Taliyah',
  'Syndra',
  'Varus',
  'Ezreal',
  'Braum',
  'Alistar',
  'Jayce',
] // fmt: skip
const ROLES = [
  'mid',
  'mid',
  'jungle',
  'bot',
  'jungle',
  'mid',
  'jungle',
  'jungle',
  'bot',
  'support',
  'support',
  'support',
]
const key = (name: string) => name.replaceAll(/[^A-Za-z]/gu, '')
const CHAMPIONS = NAMES.map((name, i) => ({ name, key: key(name), roles: [ROLES[i % ROLES.length] ?? 'top'] }))
const rate = { k: 3, n: 10, rate: 0.3, lo: 0.1, hi: 0.6 }
const comp = { champions: [], ap_share: 0.5, damage: 'mixed', totals: {}, scaling: 'mid', warnings: [] }

const ROUTES: Record<string, unknown> = {
  '/teams': [TEAM],
  '/info': { ddragon_version: '16.23.1', live_patch: '16.23', demo_protected: false },
  '/champions': CHAMPIONS,
  '/preferences': {
    team: 'Cloud9 Kia',
    weight: 0.5,
    players: [{ name: 'Blaber', role: 'jungle', wants_prio: false, pool: [{ champion: 'Vi', comfort: 'signature' }] }],
    strategy: { save_for_late_games: [], must_ban_vs_opponent: {}, never_pick: [], style_tags: [] },
  },
  '/teams/fq/scouting': {
    team: TEAM,
    period: 'recent',
    games: 12,
    draft: [
      {
        ...rate,
        champion: 'Azir',
        key: 'Azir',
        split_type: 'all',
        split: 'all',
        picks: 2,
        bans: 1,
        base_rate: 0.1,
        first_rotation: { ...rate, k: 2, rate: 0.2 },
        avg_slot: 5,
        tendency: 'weak',
      },
    ],
    targeted_players: [],
  },
  '/teams/fq/cards': [
    {
      title: 'Azir is a game-1 priority',
      claim: 'They take Azir in their first rotation in 4 of 6 game 1s.',
      evidence: [],
      action: 'Ban or take Azir early in game 1.',
      strength: 'descriptive',
      n: 6,
    },
  ],
  '/teams/fq/players': { team: TEAM, players: [] },
  '/coverage': { leagues: [], soloq: [], teams: [TEAM] },
  '/meta': {
    window: 'live',
    windows: ['live'],
    patches: ['16.17'],
    live_patch: '16.23',
    rows: [
      {
        champion: 'Azir',
        name: 'Azir',
        roles: ['mid'],
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
  },
}

const LIVE = {
  enabled: true,
  connected: true,
  phase: 'ChampSelect',
  me: 'Me#EUW',
  party: ['Me#EUW', 'Friend#EUW'],
  sample: '16.22–16.23, 1807 high-elo games',
  version: 4,
  champ_select: {
    queue: 440,
    queue_name: 'Ranked Flex',
    custom: false,
    phase: 'BAN_PICK',
    time_left_s: 24,
    allies: [
      { cell: 0, position: 'top', champion: null, intent: null, name: null, me: false, games: 0, pool: [] },
      {
        cell: 1,
        position: 'jungle',
        champion: { id: 234, name: 'Viego', key: 'Viego' },
        intent: null,
        name: 'Friend#EUW',
        me: false,
        games: 18,
        pool: [{ champion: { id: 234, name: 'Viego', key: 'Viego' }, games: 12, wins: 8, last_played: null }],
      },
      { cell: 2, position: 'mid', champion: null, intent: null, name: 'Me#EUW', me: true, games: 40, pool: [] },
    ],
    enemy_picks: [{ id: 238, name: 'Zed', key: 'Zed' }],
    ally_bans: [],
    enemy_bans: [],
    actions: [{ cell: 2, kind: 'pick', ally: true, champion: null, completed: false, in_progress: true }],
  },
  advice: {
    kind: 'pick',
    for_cell: 2,
    for_name: 'you',
    note: 'Options, not orders.',
    options: ['Orianna', 'Ahri', 'Syndra'].map((c, i) => ({
      champion: c,
      key: key(c),
      role: 'mid',
      score: 3 - i,
      parts: {},
      reasons: [`${56 - i}% adj. win rate at mid in 120 high-elo games (16.22–16.23)`],
      win_prob: null,
    })),
  },
}

function advice(body: { actions?: string[]; we_pick_first?: boolean; locked?: string[] }) {
  const actions = body.actions ?? []
  const slot = actions.length
  const free = NAMES.filter((n) => !(actions.includes(n) || body.locked?.includes(n)))
  const next =
    slot < TEMPLATE.length ? { slot, who: actor(slot, body.we_pick_first ?? true), kind: kind(slot), phase: 'p' } : null
  const options = free.slice(0, 5).map((c, i) => ({
    champion: c,
    key: key(c),
    role: null,
    score: 5 - i,
    parts: {},
    reasons: [`option ${i + 1} for slot ${slot + 1}`],
    win_prob: null,
  }))
  return {
    next,
    options: next?.who === 'us' ? options : [],
    likely: next?.who === 'them' ? options.map((o) => ({ champion: o.champion, key: o.key, probability: 0.2 })) : [],
    win_prob: { mean: 0.55, p10: 0.5, p90: 0.6, note: 'Elo-dominated' },
    our_comp: comp,
    their_comp: comp,
  }
}

/** Answer /api/* in the page (no-op against the real API). */
export async function mockApi(page: Page): Promise<void> {
  if (real) {
    return
  }
  await page.route('**/api/**', (route: Route) => {
    const url = new URL(route.request().url())
    const path = url.pathname.replace('/api', '')
    if (path === '/draft/recommend') {
      return route.fulfill({ json: advice(route.request().postDataJSON() ?? {}) })
    }
    if (path === '/lcu/state') {
      return route.fulfill({ json: LIVE })
    }
    if (path === '/series/simulate') {
      return route.fulfill({ status: 503, json: { detail: 'not in the mock' } })
    }
    return route.fulfill({ json: ROUTES[path] ?? {} })
  })
}
