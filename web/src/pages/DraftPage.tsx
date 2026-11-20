import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useId, useState } from 'react'
import { Link } from 'react-router'
import { api, type DraftAdvice, type DraftRequest } from '../api/client.ts'
import { AdvicePanel } from '../components/AdvicePanel.tsx'
import { ChampionGrid } from '../components/ChampionGrid.tsx'
import { DraftBoard } from '../components/DraftBoard.tsx'
import { Segmented } from '../components/Segmented.tsx'
import { kind, split, TEMPLATE } from '../draftOrder.ts'
import { lockedBy, type PlannedGame, useChampions, usePlan, usePrefs, weFirstNext } from '../hooks.ts'

const SIDES = [
  ['blue', 'We are blue'],
  ['red', 'We are red'],
] as const
const FIRST = [
  ['us', 'We pick first'],
  ['them', 'They pick first'],
] as const
const MODES = [
  ['best', 'Best options'],
  ['comfort_only', 'Comfort only'],
  ['save', 'Respect save list'],
] as const

const OPTION_KEY = /^[1-5]$/u

/** Keyboard shortcuts: '/' search, Backspace undo, S skip a ban, 1-5 take that option (or their likely pick). */
function shortcut(key: string, slot: number, advice: DraftAdvice | undefined): 'search' | 'undo' | string | null {
  if (key === '/') {
    return 'search'
  }
  if (key === 'Backspace') {
    return 'undo'
  }
  if (key.toLowerCase() === 's' && kind(slot) === 'ban') {
    return ''
  }
  if (!(OPTION_KEY.test(key) && advice)) {
    return null
  }
  const list = advice.next?.who === 'us' ? advice.options.map((o) => o.champion) : advice.likely.map((l) => l.champion)
  return list[Number(key) - 1] ?? null
}

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement
  )
}

export function DraftPage() {
  const teams = useQuery({ queryKey: ['teams'], queryFn: api.teams })
  const champions = useChampions()
  const [prefs] = usePrefs()
  const [plan, setPlan] = usePlan()
  const locked = lockedBy(plan)
  const [side, setSide] = useState<'blue' | 'red'>(plan.weStartBlue ? 'blue' : 'red')
  const [first, setFirst] = useState<'us' | 'them'>(weFirstNext(plan) ? 'us' : 'them')
  const [mode, setMode] = useState<DraftRequest['mode']>('best')
  const [actions, setActions] = useState<string[]>([])
  const searchId = useId()
  const gameNumber = plan.games.length + 1
  const us = prefs?.team ?? 'Cloud9 Kia'
  const opponent = teams.data?.find((t) => t.team_id === plan.opponent)
  const wePickFirst = first === 'us'
  const done = actions.length >= TEMPLATE.length

  const score = plan.games.reduce((s, g) => s + (g.result === 'won' ? 1 : 0) - (g.result === 'lost' ? 1 : 0), 0)
  const body: DraftRequest = {
    us,
    them: plan.opponent,
    we_are_blue: side === 'blue',
    we_pick_first: wePickFirst,
    actions,
    locked: [...locked.keys()],
    game_number: gameNumber,
    series_score: score,
    mode,
    preferences: prefs,
  }
  const advice = useQuery({
    queryKey: ['advice', body],
    queryFn: () => api.recommend(body),
    enabled: Boolean(plan.opponent),
    placeholderData: keepPreviousData,
  })

  const play = (c: string) => {
    if (!done) {
      setActions([...actions, c])
    }
  }
  const undo = () => setActions(actions.slice(0, -1))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) {
        return
      }
      const next = shortcut(e.key, actions.length, advice.data)
      if (next === 'search') {
        e.preventDefault()
        document.querySelector<HTMLInputElement>(`#${CSS.escape(searchId)}`)?.focus()
      } else if (next === 'undo') {
        setActions((a) => a.slice(0, -1))
      } else if (next !== null) {
        setActions((a) => [...a, next])
      }
    }
    globalThis.addEventListener('keydown', onKey)
    return () => globalThis.removeEventListener('keydown', onKey)
  }, [searchId, actions.length, advice.data])

  const record = (result: PlannedGame['result']) => {
    const s = split(actions, wePickFirst)
    const game: PlannedGame = {
      id: crypto.randomUUID(),
      ours: s.us.pick,
      theirs: s.them.pick,
      bans: [...s.us.ban, ...s.them.ban].filter(Boolean),
      result,
    }
    setPlan({ ...plan, games: [...plan.games, game] })
    setActions([])
    setFirst(result === 'lost' ? 'us' : 'them')
  }

  if (!plan.opponent) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-bold">Mock draft</h1>
        <p className="text-muted">
          Choose the opponent in the{' '}
          <Link to="/planner" className="text-primary underline">
            series planner
          </Link>{' '}
          first: the board uses its game number and Fearless locks.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">
            Mock draft: game {gameNumber} vs {opponent?.name ?? plan.opponent}
          </h1>
          <p className="text-sm text-muted">
            {locked.size} champions Fearless-locked · keys: <kbd>/</kbd> search · <kbd>1</kbd>–<kbd>5</kbd> take option
            · <kbd>Backspace</kbd> undo · <kbd>S</kbd> skip ban
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Segmented label="Our side" options={SIDES} value={side} onChange={setSide} />
          <Segmented label="First pick" options={FIRST} value={first} onChange={setFirst} />
          <Segmented label="Recommendation mode" options={MODES} value={mode} onChange={setMode} />
        </div>
      </header>
      <DraftBoard
        actions={actions}
        wePickFirst={wePickFirst}
        weAreBlue={side === 'blue'}
        ourName={us}
        theirName={opponent?.name ?? plan.opponent}
        byName={champions.byName}
      />
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={undo}
          disabled={actions.length === 0}
          className="min-h-9 cursor-pointer rounded-md border border-line px-3 text-sm disabled:opacity-40"
        >
          Undo
        </button>
        <button
          type="button"
          onClick={() => setActions([])}
          className="min-h-9 cursor-pointer rounded-md border border-line px-3 text-sm"
        >
          Reset
        </button>
        {done ? (
          <>
            <button
              type="button"
              onClick={() => record('won')}
              className="min-h-9 cursor-pointer rounded-md bg-primary px-3 text-sm font-medium text-bg"
            >
              Save to series as a win
            </button>
            <button
              type="button"
              onClick={() => record('lost')}
              className="min-h-9 cursor-pointer rounded-md border border-primary px-3 text-sm"
            >
              Save as a loss
            </button>
          </>
        ) : null}
      </div>
      <div className="grid gap-5 lg:grid-cols-[1fr_24rem]">
        <ChampionGrid
          champions={champions.list}
          taken={new Set(actions.filter(Boolean))}
          locked={locked}
          onPick={play}
          searchId={searchId}
        />
        <aside className="lg:sticky lg:top-4 lg:self-start">
          {advice.isError ? (
            <p role="alert" className="text-bad">
              {advice.error.message}
            </p>
          ) : (
            <AdvicePanel advice={advice.data} onPick={play} busy={advice.isFetching} />
          )}
        </aside>
      </div>
    </div>
  )
}
