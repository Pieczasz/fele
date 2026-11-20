import { useQuery } from '@tanstack/react-query'
import { useParams, useSearchParams } from 'react-router'
import { api, type Period, type Preferences } from './api/client.ts'
import { useLocalState } from './store.ts'

/** Data Dragon version, live patch, demo lock state. Fetched once per session. */
export function useInfo() {
  return useQuery({ queryKey: ['info'], queryFn: api.info, staleTime: Number.POSITIVE_INFINITY })
}

/** `?period=` in the URL, so a report link keeps its period. */
export function usePeriod(): [Period, (p: Period) => void] {
  const [params, setParams] = useSearchParams()
  const period: Period = params.get('period') === 'all' ? 'all' : 'recent'
  return [period, (p) => setParams({ period: p })]
}

export function useTeamId(): string {
  return useParams().teamId ?? ''
}

export function useChampions() {
  const q = useQuery({ queryKey: ['champions'], queryFn: api.champions, staleTime: Number.POSITIVE_INFINITY })
  const byName = new Map((q.data ?? []).map((c) => [c.name, c]))
  return { list: q.data ?? [], byName, query: q }
}

/** The coach's preferences: seeded from the server file, then edited and kept in this browser only. */
export function usePrefs(): [Preferences | null, (p: Preferences) => void, () => void] {
  const server = useQuery({ queryKey: ['preferences'], queryFn: api.preferences, staleTime: Number.POSITIVE_INFINITY })
  const [local, setLocal] = useLocalState<Preferences | null>('fele-prefs', null)
  const reset = () => setLocal(null)
  return [local ?? server.data ?? null, setLocal, reset]
}

export interface PlannedGame {
  id: string // stable React key (games are edited in place)
  ours: string[]
  theirs: string[]
  bans: string[]
  result: 'won' | 'lost' | null // null = planned, not played yet
}

export interface SeriesPlanState {
  opponent: string
  bestOf: 3 | 5
  weStartBlue: boolean
  games: PlannedGame[]
  save: Record<string, number> // champion -> first game we may pick it
}

export const EMPTY_PLAN: SeriesPlanState = { opponent: '', bestOf: 3, weStartBlue: true, games: [], save: {} }

export function usePlan(): [SeriesPlanState, (p: SeriesPlanState) => void] {
  return useLocalState<SeriesPlanState>('fele-plan', EMPTY_PLAN)
}

/** Games with a result. Planned games (result null) don't count toward the score, the locks or the game number. */
export function playedGames(plan: SeriesPlanState): PlannedGame[] {
  return plan.games.filter((g) => g.result !== null)
}

/**
 * Champion -> game number it was picked in (hard Fearless: unavailable for the rest of the series), from played
 * games only. `known` drops half-typed or misspelled names.
 */
export function lockedBy(plan: SeriesPlanState, known?: ReadonlyMap<string, unknown>): Map<string, number> {
  const out = new Map<string, number>()
  playedGames(plan).forEach((g, i) => {
    for (const c of [...g.ours, ...g.theirs]) {
      if (c && (!known || known.size === 0 || known.has(c))) {
        out.set(c, i + 1)
      }
    }
  })
  return out
}

/**
 * Side rule (2026 First Selection, assumed choices): game 1 as planned; afterwards the loser of the previous game
 * takes first pick and the winner chooses blue side.
 */
export function weFirstNext(plan: SeriesPlanState): boolean {
  const last = playedGames(plan).at(-1)
  return last === undefined ? plan.weStartBlue : last.result === 'lost'
}

export function weBlueNext(plan: SeriesPlanState): boolean {
  const last = playedGames(plan).at(-1)
  return last === undefined ? plan.weStartBlue : last.result === 'won'
}
