import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError, login } from './api.ts'
import { setToken } from './session.ts'

export function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const signIn = useMutation({
    mutationFn: () => login(username, password),
    onSuccess: (token) => setToken(token),
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    signIn.mutate()
  }

  return (
    <main className="login">
      <form className="card login-card" onSubmit={submit}>
        <div className="login-head">
          <h1>cloud-resource-manager</h1>
          <p className="muted">Sign in to manage and monitor your resources.</p>
        </div>
        <label>
          Username
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            required
            autoFocus
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        {signIn.isError && (
          <p className="form-error" role="alert">
            {loginErrorMessage(signIn.error)}
          </p>
        )}
        <button type="submit" className="button button-primary" disabled={signIn.isPending}>
          {signIn.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}

function loginErrorMessage(error: Error): string {
  if (!(error instanceof ApiError)) return "Can't reach the server. Is the API running?"
  if (error.status === 401) return 'Incorrect username or password.'
  if (error.status === 429) {
    const minutes = Math.ceil((error.retryAfter ?? 60) / 60)
    return `Too many failed attempts. Try again in ${minutes} minute${minutes === 1 ? '' : 's'}.`
  }
  return error.message
}
