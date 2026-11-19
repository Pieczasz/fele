import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client.ts'
import { NBadge } from '../components/Evidence.tsx'
import { QueryState, Section } from '../components/QueryState.tsx'
import { shortDate } from '../format.ts'

export function CoveragePage() {
  const query = useQuery({ queryKey: ['coverage'], queryFn: api.coverage })
  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold">Data coverage</h1>
        <p className="text-muted">How much evidence sits behind the numbers. Small samples are flagged everywhere.</p>
      </header>
      <QueryState query={query}>
        {(data) => (
          <div className="grid gap-5 lg:grid-cols-2">
            <Section title="Pro games by league" hint="GRID official data">
              <table className="w-full text-sm">
                <caption className="sr-only">Pro games per league</caption>
                <thead className="text-left text-xs text-muted">
                  <tr>
                    <th scope="col" className="py-1 font-medium">
                      League
                    </th>
                    <th scope="col" className="text-right font-medium">
                      Teams
                    </th>
                    <th scope="col" className="text-right font-medium">
                      Games
                    </th>
                    <th scope="col" className="text-right font-medium">
                      Period
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.leagues.map((l) => (
                    <tr key={l.league}>
                      <th scope="row" className="py-1.5 text-left font-normal">
                        {l.league}
                      </th>
                      <td className="tabular text-right">{l.teams}</td>
                      <td className="tabular text-right">{l.games}</td>
                      <td className="tabular text-right text-muted">
                        {shortDate(l.first_game)} – {shortDate(l.last_game)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
            <Section title="Solo queue sample" hint="Challenger + Grandmaster ranked solo, KR / EUW / NA (Riot API)">
              {data.soloq.length === 0 ? (
                <p className="text-muted">No solo-queue sample yet.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {data.soloq.map((s) => (
                    <li key={s.patch} className="flex justify-between">
                      <span>Patch {s.patch}</span>
                      <NBadge n={s.matches} unit="matches" />
                    </li>
                  ))}
                </ul>
              )}
            </Section>
            <Section title="Games per team" hint="Fewer than 20 games: read tendencies with care">
              <ul className="grid grid-cols-1 gap-x-6 text-sm sm:grid-cols-2">
                {data.teams.map((t) => (
                  <li key={t.team_id} className="flex justify-between border-b border-line py-1">
                    <span>
                      {t.name} <span className="text-xs text-muted">{t.league}</span>
                    </span>
                    <NBadge n={t.games} />
                  </li>
                ))}
              </ul>
            </Section>
          </div>
        )}
      </QueryState>
    </div>
  )
}
