import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useEffect, useId, useState } from 'react'
import { Link } from 'react-router'
import { api, type DraftAdvice, type DraftRequest } from '../api/client.ts'
import { AdvicePanel } from '../components/AdvicePanel.tsx'
import { ChampionGrid } from '../components/ChampionGrid.tsx'
import { DraftBoard } from '../components/DraftBoard.tsx'
import { Segmented } from '../components/Segmented.tsx'
import { kind, split, TEMPLATE } from '../draftOrder.ts'
import {
  lockedBy,
  type PlannedGame,
  playedGames,
  type SeriesPlanState,
  seriesScore,
  useChampions,
  usePlan,
  usePrefs,
  weBlueNext,
  weFirstNext,
} from '../hooks.ts'
import { newId, useLocalState } from '../store.ts'

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
function shortcut(e: KeyboardEvent, slot: number, advice: DraftAdvice | undefined): 'search' | 'undo' | string | null {
  const { key } = e
  if (e.ctrlKey || e.metaKey || e.altKey) {
    return null // leave browser shortcuts (Ctrl+S, Cmd+1, ...) alone
  }
  if (key === '/') {
    return 'search'
  }
  if (key === 'Backspace') {
    return 'undo'
  }
  if (key.toLowerCase() === 's' && kind(slot) === 'ban') {
    return ''
  }
  if (!(OPTION_KEY.test(key) && advice) || advice.next?.slot !== slot) {
    return null // no advice for this slot yet (still loading): never act on the previous slot's list
  }
  const list = advice.next?.who === 'us' ? advice.options.map((o) => o.champion) : advice.likely.map((l) => l.champion)
  return list[Number(key) - 1] ?? null
}

/** The draft in progress, kept across page changes and reloads for this opponent and game. */
interface StoredDraft {
  key: string // opponent:game
  actions: string[]
  side: 'blue' | 'red'
  first: 'us' | 'them'
}

/**
 * The board's draft: our own (kept per opponent and game) or, while following, the League client's custom
 * tournament draft (scrims), which runs in the same pro order.
 */
function useBoardDraft(plan: SeriesPlanState) {
  const [stored, setStored] = useLocalState<StoredDraft | null>('fele-draft', null)
  const [follow, setFollow] = useState(false)
  const live = useQuery({ queryKey: ['live'], queryFn: api.live, retry: false, refetchInterval: follow ? 1000 : 5000 })
  const client = live.data?.champ_select?.pro_draft ?? null
  const gameNumber = playedGames(plan).length + 1
  const key = `${plan.opponent}:${gameNumber}`
  const fresh = (): StoredDraft => ({
    key,
    actions: [],
    side: weBlueNext(plan) ? 'blue' : 'red', // the side rule picks the defaults for each new game
    first: weFirstNext(plan) ? 'us' : 'them',
  })
  const following = follow && client !== null
  const own = stored?.key === key ? stored : fresh()
  const draft: StoredDraft = following
    ? {
        key,
        actions: client.actions,
        side: client.we_are_blue ? 'blue' : 'red',
        first: client.we_pick_first ? 'us' : 'them',
      }
    : own
  const update = (change: (d: StoredDraft) => StoredDraft) => {
    if (!following) {
      setStored((prev) => change(prev?.key === key ? prev : fresh()))
    }
  }
  const clear = () => {
    setStored(null)
    setFollow(false)
  }
  return { draft, update, clear, gameNumber, clientDraft: client !== null, following, setFollow }
}

function isTyping(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement
  )
}

function ChampionsPanel({
  champions,
  ...grid
}: { champions: ReturnType<typeof useChampions> } & Omit<Parameters<typeof ChampionGrid>[0], 'champions'>) {
  if (champions.query.isError) {
    return (
      <p role="alert" className="text-bad">
        Couldn't load the champion list: {champions.query.error.message}
      </p>
    )
  }
  if (champions.query.isPending) {
    return (
      <p role="status" className="text-muted">
        Loading champions…
      </p>
    )
  }
  return <ChampionGrid champions={champions.list} {...grid} />
}

/** Undo / skip / reset, and saving a finished draft into the series (unless the series is already decided). */
function DraftControls({
  count,
  series,
  onUndo,
  onSkip,
  onReset,
  onRecord,
  following,
}: {
  following: boolean
  count: number
  series: ReturnType<typeof seriesScore>
  onUndo: () => void
  onSkip: () => void
  onReset: () => void
  onRecord: (result: PlannedGame['result']) => void
}) {
  const done = count >= TEMPLATE.length
  if (following && !done) {
    return (
      <p role="status" className="text-sm text-muted">
        The board follows the League client (custom tournament draft): bans and picks come from there.
      </p>
    )
  }
  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={onUndo}
        disabled={count === 0}
        className="min-h-9 cursor-pointer rounded-md border border-line px-3 text-sm disabled:opacity-40"
      >
        Undo
      </button>
      {!done && kind(count) === 'ban' ? (
        <button
          type="button"
          onClick={onSkip}
          className="min-h-9 cursor-pointer rounded-md border border-line px-3 text-sm"
        >
          Skip this ban <kbd className="text-xs text-muted">S</kbd>
        </button>
      ) : null}
      <button
        type="button"
        onClick={onReset}
        className="min-h-9 cursor-pointer rounded-md border border-line px-3 text-sm"
      >
        Reset
      </button>
      {count > 0 && !done ? (
        <span className="self-center text-xs text-muted">Sides are fixed once the draft starts (Reset to change).</span>
      ) : null}
      {done && series.over ? (
        <p className="self-center text-sm text-muted">
          The series is already decided ({series.wins}–{series.losses}). Start a new one in the{' '}
          <Link to="/planner" className="text-primary underline">
            planner
          </Link>
          .
        </p>
      ) : null}
      {done && !series.over ? (
        <>
          <button
            type="button"
            onClick={() => onRecord('won')}
            className="min-h-9 cursor-pointer rounded-md bg-primary px-3 text-sm font-medium text-bg"
          >
            Save to series as a win
          </button>
          <button
            type="button"
            onClick={() => onRecord('lost')}
            className="min-h-9 cursor-pointer rounded-md border border-primary px-3 text-sm"
          >
            Save as a loss
          </button>
        </>
      ) : null}
    </div>
  )
}

export function DraftPage() {
  const teams = useQuery({ queryKey: ['teams'], queryFn: api.teams })
  const champions = useChampions()
  const [prefs] = usePrefs()
  const [plan, setPlan] = usePlan()
  const locked = lockedBy(plan, champions.byName)
  const [mode, setMode] = useState<DraftRequest['mode']>('best')
  const board = useBoardDraft(plan)
  const searchId = useId()
  const played = playedGames(plan)
  const { gameNumber, update } = board
  const { actions, side, first } = board.draft
  const setActions = (next: (a: string[]) => string[]) => update((d) => ({ ...d, actions: next(d.actions) }))
  const series = seriesScore(plan)
  const us = prefs?.team ?? 'Cloud9 Kia'
  const opponent = teams.data?.find((t) => t.team_id === plan.opponent)
  const wePickFirst = first === 'us'

  const score = played.reduce((s, g) => s + (g.result === 'won' ? 1 : 0) - (g.result === 'lost' ? 1 : 0), 0)
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
    save: plan.save,
    preferences: prefs,
  }
  const advice = useQuery({
    queryKey: ['advice', body],
    queryFn: () => api.recommend(body),
    enabled: Boolean(plan.opponent),
    placeholderData: keepPreviousData,
  })

  // guarded with the latest state: a double click or a stale option list can't add a champion twice or a 21st action
  const append = (c: string) =>
    setActions((a) => (a.length >= TEMPLATE.length || (c !== '' && (a.includes(c) || locked.has(c))) ? a : [...a, c]))
  const reset = () => {
    if (actions.length === 0 || globalThis.confirm('Clear this draft and start the game again?')) {
      setActions(() => [])
    }
  }
  const takeOption = (c: string) => {
    if (!advice.isFetching) {
      append(c) // options belong to the slot they were computed for
    }
  }
  const undo = () => setActions((a) => a.slice(0, -1))

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTyping(e.target)) {
        return
      }
      const next = shortcut(e, actions.length, advice.isFetching ? undefined : advice.data)
      if (next === 'search') {
        e.preventDefault()
        document.querySelector<HTMLInputElement>(`#${CSS.escape(searchId)}`)?.focus()
      } else if (next === 'undo') {
        setActions((a) => a.slice(0, -1))
      } else if (next !== null) {
        append(next)
      }
    }
    globalThis.addEventListener('keydown', onKey)
    return () => globalThis.removeEventListener('keydown', onKey)
  })

  const record = (result: PlannedGame['result']) => {
    const s = split(actions, wePickFirst)
    const game: PlannedGame = {
      id: newId(),
      ours: s.us.pick,
      theirs: s.them.pick,
      bans: [...s.us.ban, ...s.them.ban].filter(Boolean),
      result,
    }
    setPlan({ ...plan, games: [...plan.games, game] }) // the next game's side and first pick follow the side rule
    board.clear()
  }

  if (!plan.opponent) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-bold">Mock draft</h1>
        <label className="flex max-w-sm flex-col gap-1 text-sm">
          <span className="font-medium">Who are we drafting against?</span>
          <select
            value=""
            onChange={(e) => setPlan({ ...plan, opponent: e.target.value })}
            className="min-h-9 rounded-md border border-line bg-surface px-2"
          >
            <option value="" disabled={true}>
              Choose an opponent…
            </option>
            {(teams.data ?? []).map((t) => (
              <option key={t.team_id} value={t.team_id}>
                {t.name} ({t.league})
              </option>
            ))}
          </select>
        </label>
        <p className="text-sm text-muted">
          This starts a series plan against them. Game numbers and Fearless locks come from the{' '}
          <Link to="/planner" className="text-primary underline">
            series planner
          </Link>
          .
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
          <Segmented
            label="Our side"
            options={SIDES}
            value={side}
            onChange={(v) => update((d) => ({ ...d, side: v }))}
            disabled={actions.length > 0 || board.following}
          />
          <Segmented
            label="First pick"
            options={FIRST}
            value={first}
            onChange={(v) => update((d) => ({ ...d, first: v }))}
            disabled={actions.length > 0 || board.following}
          />
          <Segmented label="Recommendation mode" options={MODES} value={mode} onChange={setMode} />
          {board.clientDraft ? (
            <button
              type="button"
              aria-pressed={board.following}
              onClick={() => board.setFollow(!board.following)}
              className={`min-h-9 cursor-pointer rounded-md border px-3 text-sm ${board.following ? 'border-accent font-medium' : 'border-line'}`}
            >
              {board.following ? 'Following the League client' : 'Follow the League client'}
            </button>
          ) : null}
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
      <DraftControls
        count={actions.length}
        series={series}
        onUndo={undo}
        onSkip={() => append('')}
        onReset={reset}
        onRecord={record}
        following={board.following}
      />
      <div className="grid gap-5 lg:grid-cols-[1fr_24rem]">
        <ChampionsPanel
          champions={champions}
          taken={new Set(actions.filter(Boolean))}
          locked={locked}
          onPick={append}
          searchId={searchId}
          verb={kind(actions.length) === 'ban' ? 'Ban' : 'Pick'}
        />
        <aside className="order-first lg:sticky lg:top-4 lg:order-none lg:self-start">
          {advice.isError ? (
            <p role="alert" className="text-bad">
              {advice.error.message}
            </p>
          ) : (
            <AdvicePanel advice={advice.data} onPick={takeOption} busy={advice.isFetching} />
          )}
        </aside>
      </div>
    </div>
  )
}
