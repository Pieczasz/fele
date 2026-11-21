import { expect, test as it } from 'vitest'
import { parsePlan, type SeriesPlanState, seriesScore } from './hooks.ts'

const NOT_A_PLAN = /not a fele series plan/u
const PLAN: SeriesPlanState = {
  opponent: 'fq',
  bestOf: 3,
  weStartBlue: true,
  games: [{ id: 'a', ours: ['Ahri'], theirs: ['Vi'], bans: [], result: 'won' }],
  save: { Azir: 3 },
}

it('reads back an exported plan', () => {
  expect(parsePlan(JSON.stringify(PLAN))).toEqual(PLAN)
})

it('rejects files that are not fele plans', () => {
  expect(parsePlan('not json')).toBe('This file is not JSON.')
  expect(parsePlan('{"games": "nope"}')).toMatch(NOT_A_PLAN)
  expect(parsePlan(JSON.stringify({ ...PLAN, bestOf: 7 }))).toMatch(NOT_A_PLAN)
  const badGame = { ...PLAN, games: [{ ours: [1], theirs: [], bans: [], result: 'won' }] }
  expect(parsePlan(JSON.stringify(badGame))).toMatch(NOT_A_PLAN)
})

it('fills missing ids and drops malformed save entries', () => {
  const p = parsePlan(JSON.stringify({ ...PLAN, games: [{ ...PLAN.games[0], id: undefined }], save: { Azir: 'x' } }))
  expect(p).toMatchObject({ games: [{ id: expect.any(String) }], save: {} })
})

it('knows when a series is decided', () => {
  expect(seriesScore(PLAN)).toEqual({ wins: 1, losses: 0, over: false })
  const two = { ...PLAN, games: [...PLAN.games, { ...PLAN.games[0], id: 'b' }] } as SeriesPlanState
  expect(seriesScore(two).over).toBe(true)
  expect(seriesScore({ ...two, bestOf: 5 }).over).toBe(false)
})
