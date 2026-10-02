import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { LoginPage } from './LoginPage.tsx'
import { getToken } from './session.ts'
import { mockApi, renderWithClient, reply } from './test/helpers.tsx'

async function signIn(password = 'alice-password-123') {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Username'), 'alice')
  await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('LoginPage', () => {
  it('stores the token after a successful sign-in', async () => {
    mockApi({ 'POST /auth/token': { access_token: 'token-1', token_type: 'bearer' } })
    renderWithClient(<LoginPage />)

    await signIn()

    await waitFor(() => expect(getToken()).toBe('token-1'))
  })

  it('says when the username or password is wrong', async () => {
    mockApi({ 'POST /auth/token': reply(401, { detail: 'incorrect username or password' }) })
    renderWithClient(<LoginPage />)

    await signIn('wrong-password')

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect username or password.')
    expect(getToken()).toBeNull()
  })

  it('says how long to wait when logins are paused', async () => {
    mockApi({
      'POST /auth/token': reply(429, { detail: 'too many failed logins' }, { 'Retry-After': '840' }),
    })
    renderWithClient(<LoginPage />)

    await signIn()

    expect(await screen.findByRole('alert')).toHaveTextContent('Try again in 14 minutes.')
  })

  it('says when the server cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    renderWithClient(<LoginPage />)

    await signIn()

    expect(await screen.findByRole('alert')).toHaveTextContent("Can't reach the server.")
  })
})
