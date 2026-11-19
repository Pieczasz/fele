/** Formatting shared by every page: percentages, intervals, clock times, Data Dragon image URLs. */

const DDRAGON = 'https://ddragon.leagueoflegends.com/cdn'

export function pct(x: number | null | undefined, digits = 0): string {
  return x === null || x === undefined ? '–' : `${(x * 100).toFixed(digits)}%`
}

export function interval(lo: number | null | undefined, hi: number | null | undefined): string {
  return lo === null || lo === undefined || hi === null || hi === undefined ? '' : `${pct(lo)}–${pct(hi)}`
}

export function clock(seconds: number): string {
  const s = Math.round(seconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function signed(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || x === 0) {
    return '–'
  }
  return `${x > 0 ? '+' : ''}${x.toFixed(digits)}`
}

export function championIcon(version: string, key: string): string {
  return `${DDRAGON}/${version}/img/champion/${key}.png`
}

export function mapImage(version: string): string {
  return `${DDRAGON}/${version}/img/map/map11.png`
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}
