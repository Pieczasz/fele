import type { components } from './schema'

type Schemas = components['schemas']
export type Coverage = Schemas['Coverage']
export type DraftRow = Schemas['DraftRow']
export type Health = Schemas['Health']
export type Info = Schemas['Info']
export type KillCell = Schemas['KillCell']
export type Macro = Schemas['Macro']
export type Meta = Schemas['Meta']
export type MetaRow = Schemas['MetaRow']
export type Player = Schemas['Player']
export type Players = Schemas['Players']
export type Preferences = Schemas['Preferences']
export type Rate = Schemas['Rate']
export type Scouting = Schemas['Scouting']
export type Team = Schemas['Team']
export type Period = Scouting['period']

/** The hosted demo is password protected and this browser has no session yet. */
export class LoginRequiredError extends Error {
  constructor() {
    super('Login required')
    this.name = 'LoginRequiredError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init)
  if (res.status === 401) {
    throw new LoginRequiredError()
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

const get = <T>(path: string) => request<T>(path)

export const api = {
  health: () => get<Health>('/health'),
  info: () => get<Info>('/info'),
  teams: () => get<Team[]>('/teams'),
  scouting: (teamId: string, period: Period) =>
    get<Scouting>(`/teams/${encodeURIComponent(teamId)}/scouting?period=${period}`),
  macro: (teamId: string, period: Period) => get<Macro>(`/teams/${encodeURIComponent(teamId)}/macro?period=${period}`),
  players: (teamId: string) => get<Players>(`/teams/${encodeURIComponent(teamId)}/players`),
  meta: (window: string) => get<Meta>(`/meta?window=${encodeURIComponent(window)}`),
  coverage: () => get<Coverage>('/coverage'),
  preferences: () => get<Preferences>('/preferences'),
  login: (password: string) =>
    request<undefined>('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    }),
}
