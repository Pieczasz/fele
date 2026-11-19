import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useId, useState } from 'react'
import { api } from '../api/client.ts'

export function Login() {
  const queryClient = useQueryClient()
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const inputId = useId()
  const errorId = useId()

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.login(password)
      await queryClient.invalidateQueries()
    } catch {
      setError('Wrong password. Ask the team for the demo password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto mt-16 max-w-sm space-y-4 rounded-lg border border-line bg-surface p-6">
      <h1 className="text-xl font-bold">fele demo</h1>
      <p className="text-sm text-muted">This demo is password protected.</p>
      <div className="space-y-1">
        <label htmlFor={inputId} className="block text-sm font-medium">
          Password
        </label>
        <input
          id={inputId}
          type="password"
          autoComplete="current-password"
          required={true}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          className="min-h-11 w-full rounded-md border border-line bg-bg px-3"
        />
        {error ? (
          <p id={errorId} role="alert" className="text-sm text-bad">
            {error}
          </p>
        ) : null}
      </div>
      <button
        type="submit"
        disabled={busy}
        className="min-h-11 w-full cursor-pointer rounded-md bg-primary font-medium text-bg disabled:opacity-60"
      >
        {busy ? 'Checking…' : 'Open the demo'}
      </button>
    </form>
  )
}
