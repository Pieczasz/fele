import type { ReactNode } from 'react'

/** Wide tables scroll sideways on small screens. The region is focusable, so keyboard users can scroll it too. */
export function ScrollArea({ label, children }: { label: string; children: ReactNode }) {
  return (
    // biome-ignore lint/a11y/noNoninteractiveTabindex: a scrollable region must be reachable by keyboard (WCAG 2.1.1)
    <section aria-label={label} tabIndex={0} className="overflow-x-auto">
      {children}
    </section>
  )
}
