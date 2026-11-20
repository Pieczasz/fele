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
export type ChampionInfo = Schemas['ChampionInfo']
export type DraftRequest = Schemas['DraftRequest']
export type DraftAdvice = Schemas['DraftAdvice']
export type OptionOut = Schemas['OptionOut']
export type SeriesRequest = Schemas['SeriesRequest']
export type SeriesPlan = Schemas['SeriesPlan']
export type SeriesOut = Schemas['SeriesOut']
export type Card = Schemas['Card']

/** The hosted demo is password protected and this browser has no session yet. */
export class LoginRequiredError extends Error {
  constructor() {
    super('Login required')
    this.name = 'LoginRequiredError'
  }
}

export class HttpError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'HttpError'
    this.status = status
  }
}

/** FastAPI errors: `detail` is a string, or a list of validation errors ({loc, msg}) for a 422. */
function errorMessage(body: unknown, res: Response): string {
  const detail = (body as { detail?: unknown }).detail
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`)
      .join('; ')
  }
  return `${res.status} ${res.statusText}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init)
  if (res.status === 401) {
    throw new LoginRequiredError()
  }
  if (!res.ok) {
    throw new HttpError(res.status, errorMessage(await res.json().catch(() => ({})), res))
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

const get = <T>(path: string) => request<T>(path)
const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

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
  champions: () => get<ChampionInfo[]>('/champions'),
  cards: (teamId: string) => get<Card[]>(`/teams/${encodeURIComponent(teamId)}/cards`),
  recommend: (body: DraftRequest) => post<DraftAdvice>('/draft/recommend', body),
  simulate: (body: SeriesRequest) => post<SeriesPlan>('/series/simulate', body),
  login: (password: string) =>
    request<undefined>('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    }),
}
