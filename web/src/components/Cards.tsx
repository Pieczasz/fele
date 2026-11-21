import { useQuery } from '@tanstack/react-query'
import { api, type Card } from '../api/client.ts'
import { useChampions } from '../hooks.ts'
import { ChampionIcon } from './ChampionIcon.tsx'
import { Section } from './QueryState.tsx'

const STRENGTH: Record<Card['strength'], string> = {
  strong: 'border-primary text-primary',
  weak: 'border-accent text-accent',
  model: 'border-line text-muted',
  descriptive: 'border-line text-muted',
}

/** "How to win" cards: one claim each, with its evidence and what to do with it. */
export function Cards({ teamId }: { teamId: string }) {
  const cards = useQuery({ queryKey: ['cards', teamId], queryFn: () => api.cards(teamId) })
  const champions = useChampions()
  if (cards.isPending) {
    return (
      <p role="status" className="text-muted">
        Building insights…
      </p>
    )
  }
  if (cards.isError) {
    return (
      <p role="alert" className="text-sm text-bad">
        Couldn't build the “how to win” cards: {cards.error.message}
      </p>
    )
  }
  if (cards.data.length === 0) {
    return <p className="text-sm text-muted">No pattern for this team is strong enough for a card yet.</p>
  }
  return (
    <Section title="How to win" hint="Each card: the claim, its evidence (n), what to do">
      <ul className="grid gap-3 md:grid-cols-2">
        {cards.data.map((c) => (
          <li key={c.title} className="rounded-md border border-line p-3">
            <div className="mb-1 flex items-start justify-between gap-2">
              <h3 className="font-semibold">{c.title}</h3>
              <span className={`shrink-0 rounded border px-1.5 text-xs ${STRENGTH[c.strength]}`}>{c.strength}</span>
            </div>
            <p className="text-sm">{c.detail}</p>
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="flex gap-1">
                {(c.champions ?? []).map((name) => (
                  <ChampionIcon key={name} championKey={champions.byName.get(name)?.key ?? null} size={24} />
                ))}
              </span>
              <span className="text-xs text-muted tabular">{c.evidence}</span>
            </div>
          </li>
        ))}
      </ul>
    </Section>
  )
}
