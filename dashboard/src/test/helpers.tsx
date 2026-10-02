import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { vi } from 'vitest'

type Handler = (request: { url: URL; init: RequestInit }) => unknown

// A JSON response with any status, built fresh for every request it answers.
export function reply(status: number, body: unknown, headers: Record<string, string> = {}) {
  return () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json', ...headers },
    })
}

// Stands in for the API. Routes are keyed "METHOD /path" (query strings ignored):
// a plain value is answered as 200 JSON, a function can look at the request.
export function mockApi(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(async (input: string | URL | Request, init: RequestInit = {}) => {
    const url = new URL(String(input), 'http://localhost')
    const route = routes[`${init.method ?? 'GET'} ${url.pathname}`]
    if (route === undefined) return reply(404, { detail: 'not found' })()
    const result = typeof route === 'function' ? (route as Handler)({ url, init }) : route
    return result instanceof Response ? result : Response.json(result)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}
