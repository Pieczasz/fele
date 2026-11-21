import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type DraftRow, type Scouting } from '../api/client.ts'
import { Cards } from '../components/Cards.tsx'
import { Champion, ChampionIcon } from '../components/ChampionIcon.tsx'
import { NBadge, RateBar, TendencyBadge } from '../components/Evidence.tsx'
import { QueryState, Section } from '../components/QueryState.tsx'
import { ScrollArea } from '../components/ScrollArea.tsx'
import { Segmented } from '../components/Segmented.tsx'
import { pct } from '../format.ts'
import { usePeriod, useTeamId } from '../hooks.ts'

const SPLITS = [
  ['all', 'All games'],
  ['blue', 'Blue side'],
  ['red', 'Red side'],
  ['G1', 'Game 1'],
  ['G2', 'Game 2'],
  ['G3+', 'Game 3+'],
] as const
type Split = (typeof SPLITS)[number][0]

function PriorityTable({ rows }: { rows: DraftRow[] }) {
  if (rows.length === 0) {
    return <p className="text-muted">No games in this split for the selected period.</p>
  }
  return (
    <ScrollArea label="Draft priorities">
      <table className="w-full text-sm">
        <caption className="sr-only">Champions this team picks or bans, most often first</caption>
        <thead className="text-left text-xs text-muted">
          <tr>
            <th scope="col" className="py-2 pr-3 font-medium">
              Champion
            </th>
            <th scope="col" className="pr-3 font-medium">
              Presence <span className="font-normal">(picked or banned · amber = league)</span>
            </th>
            <th scope="col" className="pr-3 text-right font-medium">
              Picks
            </th>
            <th scope="col" className="pr-3 text-right font-medium">
              Bans
            </th>
            <th scope="col" className="pr-3 text-right font-medium" title="Share of games taken in ban 1 or pick 1">
              First rotation
            </th>
            <th scope="col" className="pr-3 text-right font-medium" title="Average draft slot, 1–20 (lower = earlier)">
              Avg slot
            </th>
            <th scope="col" className="font-medium">
              vs league
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((r) => (
            <tr key={r.champion}>
              <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                <Champion name={r.champion} championKey={r.key} />
              </th>
              <td className="pr-3">
                <RateBar rate={r} base={r.base_rate} />
              </td>
              <td className="tabular pr-3 text-right">{r.picks}</td>
              <td className="tabular pr-3 text-right">{r.bans}</td>
              <td className="tabular pr-3 text-right">{pct(r.first_rotation.rate)}</td>
              <td className="tabular pr-3 text-right">{r.avg_slot?.toFixed(1) ?? '–'}</td>
              <td>
                <TendencyBadge tendency={r.tendency} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollArea>
  )
}

function Report({ data }: { data: Scouting }) {
  const [split, setSplit] = useState<Split>('all')
  const rows = data.draft.filter((r) => r.split === split)
  const games = rows[0]?.n
  return (
    <div className="space-y-5">
      <Section
        title="Draft priorities"
        hint={
          <>
            Presence with 95% interval · <NBadge n={data.games} /> in this period
          </>
        }
      >
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <Segmented label="Split" options={SPLITS} value={split} onChange={setSplit} />
          {games === undefined ? null : <NBadge n={games} />}
        </div>
        <PriorityTable rows={rows} />
      </Section>
      <Section
        title="Players opponents ban against"
        hint="Bans hitting a player's earlier pro champions, of all bans faced"
      >
        {data.targeted_players.length === 0 ? (
          <p className="text-muted">No bans in this period.</p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.targeted_players.map((p) => (
              <li key={p.player} className="rounded-md border border-line p-3">
                <p className="font-medium">
                  {p.player} <span className="text-sm font-normal text-muted">{p.role}</span>
                </p>
                <RateBar rate={p} unit="bans" />
                <ul aria-label={`Champions banned against ${p.player}`} className="mt-2 flex flex-wrap gap-2 text-xs">
                  {p.champions.map((c) => (
                    <li key={c.champion} className="inline-flex items-center gap-1">
                      <ChampionIcon championKey={c.key} size={22} />
                      {c.champion} ×{c.count}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  )
}

export function ScoutingPage() {
  const teamId = useTeamId()
  const [period] = usePeriod()
  const query = useQuery({ queryKey: ['scouting', teamId, period], queryFn: () => api.scouting(teamId, period) })
  return (
    <div className="space-y-5">
      <Cards teamId={teamId} />
      <QueryState query={query}>{(data) => <Report data={data} />}</QueryState>
    </div>
  )
}
