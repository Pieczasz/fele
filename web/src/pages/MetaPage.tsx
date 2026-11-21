import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { api, type Meta } from '../api/client.ts'
import { Champion } from '../components/ChampionIcon.tsx'
import { NBadge, RateBar } from '../components/Evidence.tsx'
import { QueryState, Section } from '../components/QueryState.tsx'
import { ScrollArea } from '../components/ScrollArea.tsx'
import { Segmented } from '../components/Segmented.tsx'
import { interval, pct, signed } from '../format.ts'

const ROLES = [
  ['any', 'All roles'],
  ['top', 'Top'],
  ['jungle', 'Jungle'],
  ['mid', 'Mid'],
  ['bot', 'Bot'],
  ['support', 'Support'],
] as const
type RoleFilter = (typeof ROLES)[number][0]

function WinRate({
  value,
  lo,
  hi,
  n,
}: {
  value: number | null
  lo: number | null
  hi: number | null
  n: number | null
}) {
  if (value === null || n === null) {
    return <span className="text-muted">–</span>
  }
  return (
    <span className="inline-flex items-center justify-end gap-2" title={`95% ${interval(lo, hi)}`}>
      <span className="tabular">{pct(value, 1)}</span>
      <NBadge n={n} />
    </span>
  )
}

function MetaTable({ data }: { data: Meta }) {
  const [role, setRole] = useState<RoleFilter>('any')
  const rows = data.rows.filter((r) => role === 'any' || r.roles.includes(role))
  return (
    <Section
      title={data.window === 'live' ? `Live meta (patch ${data.live_patch ?? '?'})` : `Patch ${data.window}`}
      hint={`Pro games from patches ${data.patches.join(', ')}`}
    >
      <div className="mb-3">
        <Segmented label="Role" options={ROLES} value={role} onChange={setRole} />
      </div>
      <ScrollArea label="Meta table">
        <table className="w-full text-sm">
          <caption className="sr-only">Champions ranked by meta score</caption>
          <thead className="text-left text-xs text-muted">
            <tr>
              <th scope="col" className="py-2 pr-3 font-medium">
                Champion
              </th>
              <th scope="col" className="pr-3 font-medium">
                Pro presence
              </th>
              <th
                scope="col"
                className="pr-3 text-right font-medium"
                title="Shrunk toward the average; most pro win rates are noise"
              >
                Pro win rate
              </th>
              <th
                scope="col"
                className="pr-3 text-right font-medium"
                title="Challenger/Grandmaster ranked solo, KR/EUW/NA"
              >
                Solo queue
              </th>
              <th
                scope="col"
                className="pr-3 text-right font-medium"
                title="Data Dragon stat/cooldown changes since the window"
              >
                Patch change
              </th>
              <th
                scope="col"
                className="text-right font-medium"
                title="0.5·presence + 0.25·pro WR + 0.15·solo queue + 0.1·patch (z-scores)"
              >
                Meta score
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => (
              <tr key={r.champion}>
                <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                  <Champion name={r.name ?? r.champion} championKey={r.champion} />
                </th>
                <td className="pr-3">
                  <RateBar rate={r.presence} />
                </td>
                <td className="pr-3 text-right">
                  <WinRate value={r.pro_wr} lo={r.pro_wr_lo} hi={r.pro_wr_hi} n={r.pro_n} />
                </td>
                <td className="pr-3 text-right">
                  <WinRate value={r.soloq_wr} lo={r.soloq_wr_lo} hi={r.soloq_wr_hi} n={r.soloq_n} />
                </td>
                <td className="tabular pr-3 text-right">{signed(r.delta)}</td>
                <td className="tabular text-right font-semibold">{r.meta_score.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollArea>
    </Section>
  )
}

export function MetaPage() {
  const [params, setParams] = useSearchParams()
  const window = params.get('window') ?? 'live'
  const query = useQuery({ queryKey: ['meta', window], queryFn: () => api.meta(window) })
  const windows = query.data?.windows ?? ['live']
  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Meta</h1>
          <p className="text-muted">What pros prioritise and what is winning in high-elo solo queue right now.</p>
        </div>
        <label className="text-sm">
          <span className="mr-2 text-muted">Patch window</span>
          <select
            value={window}
            onChange={(e) => setParams({ window: e.target.value })}
            className="min-h-9 rounded-md border border-line bg-surface px-2"
          >
            {[...windows].reverse().map((w) => (
              <option key={w} value={w}>
                {w === 'live' ? 'Live (latest pro + solo queue)' : `Patch ${w}`}
              </option>
            ))}
          </select>
        </label>
      </header>
      <QueryState query={query}>{(data) => <MetaTable data={data} />}</QueryState>
    </div>
  )
}
