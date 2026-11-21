import { useMemo, useState } from 'react'
import type { ChampionInfo } from '../api/client.ts'
import { matchesChampion } from '../champions.ts'
import { ChampionIcon } from './ChampionIcon.tsx'
import { Segmented } from './Segmented.tsx'

const ROLES = [
  ['all', 'All'],
  ['top', 'Top'],
  ['jungle', 'Jungle'],
  ['mid', 'Mid'],
  ['bot', 'Bot'],
  ['support', 'Support'],
] as const
type RoleFilter = (typeof ROLES)[number][0]

function matches(c: ChampionInfo, query: string, role: RoleFilter): boolean {
  return (role === 'all' || c.roles.includes(role)) && matchesChampion(c.name, query)
}

/**
 * Searchable champion grid. Taken champions (this game) and Fearless-locked ones (earlier games, with the game number)
 * are greyed out and can't be chosen. Enter in the search box picks the first available match.
 */
export function ChampionGrid({
  champions,
  taken,
  locked,
  onPick,
  searchId,
}: {
  champions: ChampionInfo[]
  taken: Set<string>
  locked: Map<string, number>
  onPick: (name: string) => void
  searchId: string
}) {
  const [query, setQuery] = useState('')
  const [role, setRole] = useState<RoleFilter>('all')
  const visible = useMemo(() => champions.filter((c) => matches(c, query, role)), [champions, query, role])
  const available = (c: ChampionInfo) => !(taken.has(c.name) || locked.has(c.name))

  return (
    <section aria-label="Champions" className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted">Search</span>
          <input
            id={searchId}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              const first = visible.find(available)
              if (e.key === 'Enter' && first) {
                onPick(first.name)
                setQuery('')
              }
            }}
            placeholder="name or nickname, Enter"
            className="min-h-9 w-44 rounded-md border border-line bg-surface px-2"
          />
        </label>
        <Segmented label="Role" options={ROLES} value={role} onChange={setRole} />
      </div>
      <ul className="grid grid-cols-[repeat(auto-fill,minmax(4.5rem,1fr))] gap-1.5">
        {visible.map((c) => {
          const game = locked.get(c.name)
          const free = available(c)
          return (
            <li key={c.name}>
              <button
                type="button"
                disabled={!free}
                onClick={() => onPick(c.name)}
                title={game === undefined ? c.name : `${c.name}: picked in game ${game} (Fearless)`}
                className="relative flex w-full cursor-pointer flex-col items-center gap-0.5 rounded-md p-1 text-[11px] hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-35"
              >
                <ChampionIcon championKey={c.key} size={40} />
                <span className="w-full truncate text-center">{c.name}</span>
                {game === undefined ? null : (
                  <span className="absolute top-0.5 right-0.5 rounded bg-ink px-1 text-[10px] text-bg">G{game}</span>
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
