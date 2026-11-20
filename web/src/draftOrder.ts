/** The pro draft order (validated in the engine, Phase 2). A = the first-pick team, which may be red since 2026. */
export const TEMPLATE: readonly (readonly ['ban' | 'pick', 'A' | 'B'])[] = [
  ...(['A', 'B', 'A', 'B', 'A', 'B'] as const).map((t) => ['ban', t] as const),
  ...(['A', 'B', 'B', 'A', 'A', 'B'] as const).map((t) => ['pick', t] as const),
  ...(['B', 'A', 'B', 'A'] as const).map((t) => ['ban', t] as const),
  ...(['B', 'A', 'A', 'B'] as const).map((t) => ['pick', t] as const),
]

export type Side = 'us' | 'them'

export function actor(slot: number, wePickFirst: boolean): Side {
  const team = TEMPLATE[slot]?.[1]
  return (team === 'A') === wePickFirst ? 'us' : 'them'
}

export function kind(slot: number): 'ban' | 'pick' {
  return TEMPLATE[slot]?.[0] ?? 'pick'
}

/** Champions per side and action, in draft order, from the list of actions so far. */
export function split(actions: string[], wePickFirst: boolean) {
  const out = { us: { ban: [] as string[], pick: [] as string[] }, them: { ban: [] as string[], pick: [] as string[] } }
  actions.forEach((c, i) => {
    out[actor(i, wePickFirst)][kind(i)].push(c)
  })
  return out
}
