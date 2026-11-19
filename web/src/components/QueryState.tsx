import type { UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { LoginRequiredError } from '../api/client.ts'

/** Loading / error / data switch shared by every page. A 401 is handled once, by the app shell. */
export function QueryState<T>({ query, children }: { query: UseQueryResult<T>; children: (data: T) => ReactNode }) {
  if (query.isPending) {
    return (
      <p role="status" className="py-10 text-muted">
        Loading…
      </p>
    )
  }
  if (query.isError) {
    if (query.error instanceof LoginRequiredError) {
      return null
    }
    return (
      <p role="alert" className="rounded border border-bad p-4 text-bad">
        Couldn't load this view: {query.error.message}
      </p>
    )
  }
  return <>{children(query.data)}</>
}

export function Section({ title, hint, children }: { title: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-surface p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold">{title}</h2>
        {hint ? <p className="text-xs text-muted">{hint}</p> : null}
      </div>
      {children}
    </section>
  )
}
