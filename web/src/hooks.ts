import { useQuery } from '@tanstack/react-query'
import { useParams, useSearchParams } from 'react-router'
import { api, type Period } from './api/client.ts'

/** Data Dragon version, live patch, demo lock state. Fetched once per session. */
export function useInfo() {
  return useQuery({ queryKey: ['info'], queryFn: api.info, staleTime: Number.POSITIVE_INFINITY })
}

/** `?period=` in the URL, so a report link keeps its period. */
export function usePeriod(): [Period, (p: Period) => void] {
  const [params, setParams] = useSearchParams()
  const period: Period = params.get('period') === 'all' ? 'all' : 'recent'
  return [period, (p) => setParams({ period: p })]
}

export function useTeamId(): string {
  return useParams().teamId ?? ''
}
