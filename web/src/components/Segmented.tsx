/** A row of mutually exclusive buttons (period, side, game number). Uses aria-pressed, so it reads as toggles. */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: readonly (readonly [T, string])[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <fieldset className="inline-flex flex-wrap items-center gap-1">
      <legend className="sr-only">{label}</legend>
      {options.map(([v, text]) => (
        <button
          key={v}
          type="button"
          aria-pressed={v === value}
          onClick={() => onChange(v)}
          className={`min-h-9 cursor-pointer rounded-md border px-3 text-sm motion-safe:transition-colors motion-safe:duration-150 ${
            v === value
              ? 'border-primary bg-primary-soft font-medium text-ink'
              : 'border-line text-muted hover:text-ink'
          }`}
        >
          {text}
        </button>
      ))}
    </fieldset>
  )
}
