/** Champion name matching for every place a coach types a name: punctuation and case don't matter ("kaisa" finds
 * Kai'Sa, "ksante" finds K'Sante), common nicknames work ("mf", "tf", "j4"), and a unique prefix is enough. */

const ALIASES: Record<string, string> = {
  asol: 'Aurelion Sol',
  belveth: "Bel'Veth",
  cass: 'Cassiopeia',
  cait: 'Caitlyn',
  ez: 'Ezreal',
  gp: 'Gangplank',
  heca: 'Hecarim',
  j4: 'Jarvan IV',
  kass: 'Kassadin',
  kog: "Kog'Maw",
  lb: 'LeBlanc',
  liss: 'Lissandra',
  malph: 'Malphite',
  mf: 'Miss Fortune',
  morg: 'Morgana',
  mundo: 'Dr. Mundo',
  naut: 'Nautilus',
  noc: 'Nocturne',
  nunu: 'Nunu & Willump',
  ori: 'Orianna',
  renata: 'Renata Glasc',
  sej: 'Sejuani',
  tf: 'Twisted Fate',
  tk: 'Tahm Kench',
  trist: 'Tristana',
  trynd: 'Tryndamere',
  vlad: 'Vladimir',
  voli: 'Volibear',
  wu: 'Wukong',
  ww: 'Warwick',
  xin: 'Xin Zhao',
  yi: 'Master Yi',
}

export function normalize(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]/gu, '')
}

/** Grid search: does this champion match what was typed (substring of the normalised name, or a nickname)? */
export function matchesChampion(name: string, query: string): boolean {
  const q = normalize(query)
  return q === '' || normalize(name).includes(q) || ALIASES[q] === name
}

/** The canonical name for typed text, or null when it matches no champion (or more than one by prefix). */
export function resolveChampion(text: string, names: readonly string[]): string | null {
  const q = normalize(text)
  if (q === '') {
    return null
  }
  const exact = names.find((n) => normalize(n) === q)
  if (exact) {
    return exact
  }
  const alias = ALIASES[q]
  if (alias && names.includes(alias)) {
    return alias
  }
  const prefixed = names.filter((n) => normalize(n).startsWith(q))
  return prefixed.length === 1 ? (prefixed[0] ?? null) : null
}
