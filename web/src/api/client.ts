import type { components } from './schema'

export type Preferences = components['schemas']['Preferences']
export type Health = components['schemas']['Health']

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`)
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} on ${path}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => get<Health>('/health'),
  preferences: () => get<Preferences>('/preferences'),
}
