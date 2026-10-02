import { describe, expect, it } from 'vitest'
import { ApiError, createResource, listResources, login } from './api.ts'
import { getToken, setToken } from './session.ts'
import { mockApi, reply } from './test/helpers.tsx'

describe('api', () => {
  it('signs requests with the current token', async () => {
    setToken('token-1')
    const fetchMock = mockApi({ 'GET /resources': [] })

    await listResources()

    const init = fetchMock.mock.calls[0][1]
    expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer token-1')
  })

  it('signs the user out when the server rejects their token', async () => {
    setToken('expired')
    mockApi({ 'GET /resources': reply(401, { detail: 'invalid or expired token' }) })

    await expect(listResources()).rejects.toBeInstanceOf(ApiError)
    expect(getToken()).toBeNull()
  })

  it('sends the login as a form and returns the token', async () => {
    const fetchMock = mockApi({ 'POST /auth/token': { access_token: 'token-2', token_type: 'bearer' } })

    expect(await login('alice', 'alice-password-123')).toBe('token-2')
    expect(String(fetchMock.mock.calls[0][1]?.body)).toBe('username=alice&password=alice-password-123')
  })

  it('reports how long to wait when logins are paused', async () => {
    mockApi({
      'POST /auth/token': reply(429, { detail: 'too many failed logins' }, { 'Retry-After': '840' }),
    })

    await expect(login('alice', 'guess')).rejects.toMatchObject({ status: 429, retryAfter: 840 })
  })

  it('turns a validation error into a readable message', async () => {
    setToken('token-1')
    mockApi({
      'POST /resources': reply(422, { detail: [{ loc: ['body', 'name'], msg: 'String too short' }] }),
    })

    await expect(createResource('a', 'nginx')).rejects.toThrow('String too short')
  })
})
