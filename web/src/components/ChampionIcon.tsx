import { championIcon } from '../format.ts'
import { useInfo } from '../hooks.ts'

/** Data Dragon square icon with a fixed size (no layout shift). Decorative: the name is always printed next to it. */
export function ChampionIcon({ championKey, size = 28 }: { championKey: string | null; size?: number }) {
  const version = useInfo().data?.ddragon_version
  const box = { width: size, height: size }
  if (!(version && championKey)) {
    return <span aria-hidden="true" className="inline-block shrink-0 rounded bg-surface-2" style={box} />
  }
  return (
    <img
      src={championIcon(version, championKey)}
      alt=""
      loading="lazy"
      decoding="async"
      width={size}
      height={size}
      className="shrink-0 rounded"
      style={box}
    />
  )
}

/** Icon + name; the name is the accessible text, so the icon itself is decorative. */
export function Champion({ name, championKey }: { name: string; championKey: string | null }) {
  return (
    <span className="inline-flex items-center gap-2">
      <ChampionIcon championKey={championKey} />
      <span>{name}</span>
    </span>
  )
}
