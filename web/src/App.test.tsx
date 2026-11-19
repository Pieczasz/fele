import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, expect, test as it, vi } from 'vitest'
import { App } from './App.tsx'
import { RIOT_BOILERPLATE } from './legal.ts'

const API_OK = /API: ok/

afterEach(() => {
  vi.unstubAllGlobals()
})

it('shows API health and Riot boilerplate', async () => {
  const fakeFetch = vi.fn((url: string) => {
    const body = url.endsWith('/health') ? { status: 'ok', service: 'x' } : { team: 'T', players: [] }
    return Promise.resolve(Response.json(body))
  })
  vi.stubGlobal('fetch', fakeFetch)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  expect(await screen.findByText(API_OK)).toBeInTheDocument()
  expect(screen.getByText(RIOT_BOILERPLATE)).toBeInTheDocument()
})
