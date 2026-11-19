import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { App } from './App.tsx'
import './index.css'
import { applyTheme, initialTheme } from './theme.ts'

applyTheme(initialTheme())

// aggregates change only when `fele stats` reruns: no refetching on every focus
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60_000, refetchOnWindowFocus: false } },
})

const root = document.querySelector('#root')
if (!root) {
  throw new Error('#root element missing from index.html')
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
