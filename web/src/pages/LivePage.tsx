import { useQuery } from '@tanstack/react-query'
import { api, type ChampRef, type LiveAlly, type LiveState } from '../api/client.ts'
import { ChampionIcon } from '../components/ChampionIcon.tsx'
import { NBadge } from '../components/Evidence.tsx'
import { QueryState, Section } from '../components/QueryState.tsx'

const POSITION: Record<string, string> = { top: 'Top', jungle: 'Jungle', mid: 'Mid', bot: 'Bot', support: 'Support' }
const PHASE: Record<string, string> = {
  None: 'In the client',
  Lobby: 'In a lobby',
  Matchmaking: 'Looking for a match',
  ReadyCheck: 'Match found',
  ChampSelect: 'Champ select',
  InProgress: 'In game',
  WaitingForStats: 'Game over',
  EndOfGame: 'Game over',
}

function Chip({ c, muted = false }: { c: ChampRef; muted?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 ${muted ? 'opacity-60' : ''}`}>
      <ChampionIcon championKey={c.key} size={24} />
      <span>{c.name}</span>
    </span>
  )
}

function Setup({ enabled }: { enabled: boolean }) {
  return (
    <Section title={enabled ? 'Waiting for the League client' : 'fele Live is off'}>
      {enabled ? (
        <p className="text-sm text-muted">
          Open League of Legends on this computer. fele finds the client by itself and follows your lobby and champ
          select.
        </p>
      ) : (
        <div className="space-y-2 text-sm text-muted">
          <p>fele Live reads champ select from the League client running on this computer. Start the API with it:</p>
          <pre className="overflow-x-auto rounded bg-surface-2 p-2 text-ink">cd engine && uv run fele serve --lcu</pre>
        </div>
      )}
      <p className="mt-3 text-xs text-muted">
        Privacy: fele shows names and recent games only for you and your party. Other teammates appear as “Ally”, and
        the enemy team is never looked up. Nothing leaves this computer.
      </p>
    </Section>
  )
}

function AllyRow({ a, active }: { a: LiveAlly; active: boolean }) {
  const who = a.me ? 'You' : (a.name?.split('#')[0] ?? 'Ally')
  return (
    <li
      className={`rounded-md border p-2 ${active ? 'border-accent' : 'border-line'}`}
      aria-current={active ? 'step' : undefined}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="w-16 text-xs text-muted">{a.position ? POSITION[a.position] : '—'}</span>
        <span className="font-semibold">{who}</span>
        {active ? <span className="text-xs text-accent">picking now</span> : null}
        <span className="ml-auto">
          {a.champion ? <Chip c={a.champion} /> : null}
          {!a.champion && a.intent ? <Chip c={a.intent} muted={true} /> : null}
        </span>
      </div>
      {a.pool.length > 0 ? (
        <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
          <span>Last {a.games} games (won/played):</span>
          {a.pool.map((p) => (
            <span key={p.champion.id} className="inline-flex items-center gap-1">
              <ChampionIcon championKey={p.champion.key} size={18} />
              <span>{p.champion.name}</span>
              <NBadge k={p.wins} n={p.games} unit="games won" />
            </span>
          ))}
        </p>
      ) : null}
    </li>
  )
}

function forWhom(name: string | null): string {
  if (name === 'you') {
    return 'for you'
  }
  return name ? `for ${name.split('#')[0]}` : 'for this ally'
}

function ChampSelectView({ s }: { s: LiveState }) {
  const cs = s.champ_select
  if (!cs) {
    return null
  }
  const current = cs.actions.find((a) => a.in_progress && !a.completed)
  const advice = s.advice
  const title = advice ? `${advice.kind === 'ban' ? 'Ban' : 'Pick'} options ${forWhom(advice.for_name)}` : 'Options'
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
      <div className="space-y-4">
        <Section title="Your team" hint={`${cs.queue_name}${cs.custom ? ' · custom' : ''}`}>
          <ol className="space-y-2">
            {cs.allies.map((a) => (
              <AllyRow key={a.cell} a={a} active={current?.ally === true && current.cell === a.cell} />
            ))}
          </ol>
        </Section>
        <Section title="Bans and enemy picks">
          <dl className="space-y-2 text-sm">
            {(
              [
                ['Our bans', cs.ally_bans],
                ['Their bans', cs.enemy_bans],
                ['Their picks', cs.enemy_picks],
              ] as const
            ).map(([label, list]) => (
              <div key={label} className="flex flex-wrap items-center gap-2">
                <dt className="w-24 text-xs text-muted">{label}</dt>
                <dd className="flex flex-wrap gap-3">
                  {list.length ? (
                    list.map((c) => <Chip key={c.id} c={c} />)
                  ) : (
                    <span className="text-muted">none yet</span>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </Section>
      </div>
      <Section title={title} hint={`${Math.max(0, Math.round(cs.time_left_s))} s left`}>
        <div aria-live="polite">
          {advice && advice.options.length > 0 ? (
            <ol className="space-y-2">
              {advice.options.map((o, i) => (
                <li key={o.champion} className="rounded-md border border-line p-2">
                  <div className="flex items-center gap-2">
                    <span className="w-5 text-xs text-muted">{i + 1}</span>
                    <ChampionIcon championKey={o.key} size={32} />
                    <span className="font-semibold">{o.champion}</span>
                    {o.role ? <span className="text-xs text-muted">{POSITION[o.role] ?? o.role}</span> : null}
                  </div>
                  <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-muted">
                    {o.reasons.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-muted">Nothing to decide right now.</p>
          )}
        </div>
        <p className="mt-3 text-xs text-muted">
          {advice?.note ?? ''} Sample: {s.sample}.
        </p>
      </Section>
    </div>
  )
}

/** fele Live: follows the League client on this computer (lobby → champ select) and offers ranked options. */
export function LivePage() {
  const live = useQuery({ queryKey: ['live'], queryFn: api.live, refetchInterval: 1000 })
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">fele Live</h1>
        <p className="text-sm text-muted">Champ select help for your own games: solo/duo, flex and Clash.</p>
      </div>
      <QueryState query={live}>
        {(s) =>
          s.connected ? (
            <>
              <p role="status" className="text-sm">
                <span className="font-semibold">Client connected</span>
                {s.me ? ` as ${s.me}` : ''} · {PHASE[s.phase ?? ''] ?? s.phase}
                {s.party.length > 1 ? ` · party: ${s.party.map((p) => p.split('#')[0]).join(', ')}` : ''}
              </p>
              {s.champ_select ? (
                <ChampSelectView s={s} />
              ) : (
                <Section title="Ready">
                  <p className="text-sm text-muted">
                    Advice appears here when champ select starts. Your party's recent games are loaded in the lobby, so
                    it is instant.
                  </p>
                </Section>
              )}
            </>
          ) : (
            <Setup enabled={s.enabled} />
          )
        }
      </QueryState>
    </div>
  )
}
