import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type KillCell, type Macro } from '../api/client.ts'
import { NBadge, RateBar, TendencyBadge } from '../components/Evidence.tsx'
import { QueryState, Section } from '../components/QueryState.tsx'
import { Segmented } from '../components/Segmented.tsx'
import { clock, mapImage } from '../format.ts'
import { useInfo, usePeriod, useTeamId } from '../hooks.ts'

const METRICS: Record<string, string> = {
  jungle_top_start: 'Jungler starts on the top half',
  got_first_scuttle: 'Takes the first scuttle',
  got_first_blood: 'Gets first blood',
  got_first_tower: 'Takes the first tower',
  got_first_drake: 'Takes the first drake',
  got_first_grubs: 'Takes the first grubs',
  got_first_herald: 'Takes the first herald',
  grubs_before_drake: 'Grubs before drake',
}
const TIMINGS: Record<string, string> = {
  jungle_l2_s: 'Jungler level 2',
  scuttle_s: 'First scuttle',
  grubs_s: 'First grubs',
  drake_s: 'First drake',
  herald_s: 'First herald',
  tower_s: 'First tower',
}
const SPLITS = [
  ['all', 'Both sides'],
  ['blue', 'Blue'],
  ['red', 'Red'],
] as const
const KINDS = [
  ['kill', 'Kills'],
  ['death', 'Deaths'],
] as const
const SIDES = [
  ['blue', 'Blue side'],
  ['red', 'Red side'],
] as const

const MAP_PX = 320
const MAP_UNITS = 15_000
const CELL_UNITS = 1000
const CELL_PX = (CELL_UNITS / MAP_UNITS) * MAP_PX

function Heatmap({ cells, version, label }: { cells: KillCell[]; version: string | null; label: string }) {
  const max = Math.max(1, ...cells.map((c) => c.count))
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${MAP_PX} ${MAP_PX}`}
      width={MAP_PX}
      height={MAP_PX}
      className="max-w-full rounded-md border border-line"
    >
      {version ? <image href={mapImage(version)} width={MAP_PX} height={MAP_PX} opacity={0.55} /> : null}
      {cells.map((c) => (
        <rect
          key={`${c.cx}-${c.cy}`}
          x={c.cx * CELL_PX}
          y={MAP_PX - (c.cy + 1) * CELL_PX}
          width={CELL_PX}
          height={CELL_PX}
          fill="rgb(var(--heat))"
          fillOpacity={0.15 + 0.75 * (c.count / max)}
        >
          <title>{`${c.count}`}</title>
        </rect>
      ))}
    </svg>
  )
}

function Report({ data }: { data: Macro }) {
  const [split, setSplit] = useState<(typeof SPLITS)[number][0]>('all')
  const [side, setSide] = useState<(typeof SIDES)[number][0]>('blue')
  const [kind, setKind] = useState<(typeof KINDS)[number][0]>('kill')
  const version = useInfo().data?.ddragon_version ?? null
  const rates = data.rates.filter((r) => r.split === split)
  const cells = data.early_kills.filter((c) => c.side === side && c.kind === kind)
  const total = cells.reduce((s, c) => s + c.count, 0)
  const sideGames = data.games_by_side[side] ?? 0
  return (
    <div className="space-y-5">
      <Section
        title="Early game habits"
        hint="Amber tick = league average · positions are event snapshots, not tracking"
      >
        <div className="mb-3">
          <Segmented label="Side" options={SPLITS} value={split} onChange={setSplit} />
        </div>
        <table className="w-full text-sm">
          <caption className="sr-only">Early game rates compared with the league</caption>
          <tbody className="divide-y divide-line">
            {rates.map((r) => (
              <tr key={r.metric}>
                <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                  {METRICS[r.metric] ?? r.metric}
                </th>
                <td className="pr-3">
                  <RateBar rate={r} base={r.base_rate} />
                </td>
                <td>
                  <TendencyBadge tendency={r.tendency} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Objective timings" hint="Team's own first, median (middle half of games)">
          <table className="w-full text-sm">
            <caption className="sr-only">Median time of the team's first objectives</caption>
            <tbody className="divide-y divide-line">
              {data.timings.map((t) => (
                <tr key={t.metric}>
                  <th scope="row" className="py-1.5 text-left font-normal">
                    {TIMINGS[t.metric] ?? t.metric}
                  </th>
                  <td className="tabular text-right font-medium">{clock(t.median_s)}</td>
                  <td className="tabular pl-2 text-right text-muted">
                    {clock(t.q25_s)}–{clock(t.q75_s)}
                  </td>
                  <td className="pl-2 text-right">
                    <NBadge n={t.n} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
        <Section title="Where the first 15 minutes are fought" hint={<NBadge n={sideGames} />}>
          <div className="mb-3 flex flex-wrap gap-3">
            <Segmented label="Side" options={SIDES} value={side} onChange={setSide} />
            <Segmented label="Kills or deaths" options={KINDS} value={kind} onChange={setKind} />
          </div>
          <Heatmap
            cells={cells}
            version={version}
            label={`${total} ${kind === 'kill' ? 'kills' : 'deaths'} before 15:00 on ${side} side in ${sideGames} games; darker squares had more`}
          />
          <p className="mt-2 text-xs text-muted">
            {total} {kind === 'kill' ? 'kills' : 'deaths'} in {sideGames} games. Blue base bottom-left.
          </p>
        </Section>
      </div>
    </div>
  )
}

export function MacroPage() {
  const teamId = useTeamId()
  const [period] = usePeriod()
  const query = useQuery({ queryKey: ['macro', teamId, period], queryFn: () => api.macro(teamId, period) })
  return <QueryState query={query}>{(data) => <Report data={data} />}</QueryState>
}
