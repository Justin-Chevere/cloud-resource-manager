import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import type { LatestMetric, Resource, Role } from './api.ts'
import { Dashboard } from './Dashboard.tsx'
import { MiB } from './format.ts'
import { getToken, setToken } from './session.ts'
import { mockApi, renderWithClient } from './test/helpers.tsx'

const now = new Date().toISOString()

const web: Resource = {
  id: 'r1',
  name: 'web-1',
  image: 'nginx:latest',
  desired_state: 'running',
  actual_state: 'running',
  created_at: now,
  updated_at: now,
}
const batch: Resource = {
  ...web,
  id: 'r2',
  name: 'batch-1',
  image: 'python:3.14',
  desired_state: 'stopped',
  actual_state: 'stopped',
}

const readings: LatestMetric[] = [
  { resource_id: 'r1', name: 'web-1', collected_at: now, cpu_percent: 25, memory_bytes: 248 * MiB },
  // batch-1 is stopped, so this is its last reading from before it stopped.
  { resource_id: 'r2', name: 'batch-1', collected_at: now, cpu_percent: 80, memory_bytes: 512 * MiB },
]

function serve(role: Role, extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /auth/me': { id: 'u1', username: `${role}-user`, role, is_active: true, created_at: now },
    'GET /resources': [web, batch],
    'GET /metrics/latest': readings,
    'GET /audit': [
      {
        id: 1,
        created_at: now,
        actor: 'admin',
        action: 'resource.create',
        target_id: 'r1',
        details: { name: 'web-1', image: 'nginx:latest' },
      },
    ],
    ...extra,
  })
}

beforeEach(() => setToken('token-1'))

describe('Dashboard', () => {
  it('lists resources with their status and live readings', async () => {
    serve('viewer')
    renderWithClient(<Dashboard />)

    const row = await screen.findByRole('row', { name: /web-1/ })
    expect(within(row).getByText('Running')).toBeInTheDocument()
    expect(await within(row).findByText('25%')).toBeInTheDocument()
    expect(within(row).getByText('248 MiB')).toBeInTheDocument()
  })

  it("doesn't pass off a stopped resource's last reading as current", async () => {
    serve('viewer')
    renderWithClient(<Dashboard />)

    expect(await screen.findByText('0.25 cores')).toBeInTheDocument()
    const row = screen.getByRole('row', { name: /batch-1/ })
    expect(within(row).queryByText('80%')).not.toBeInTheDocument()
    expect(within(row).getAllByText('No reading')).toHaveLength(2)
  })

  it('gives viewers no controls', async () => {
    serve('viewer')
    renderWithClient(<Dashboard />)

    await screen.findByRole('row', { name: /web-1/ })
    expect(screen.queryByRole('button', { name: 'Stop web-1' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'New resource' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Recent activity' })).not.toBeInTheDocument()
  })

  it('lets operators stop a resource', async () => {
    const fetchMock = serve('operator', { 'PATCH /resources/r1': { ...web, desired_state: 'stopped' } })
    renderWithClient(<Dashboard />)

    await userEvent.setup().click(await screen.findByRole('button', { name: 'Stop web-1' }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/resources/r1',
        expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ desired_state: 'stopped' }) }),
      ),
    )
  })

  it('asks for confirmation before deleting', async () => {
    const fetchMock = serve('operator', { 'DELETE /resources/r1': { ...web, desired_state: 'deleted' } })
    renderWithClient(<Dashboard />)
    const user = userEvent.setup()
    const deleteCall = ['/resources/r1', expect.objectContaining({ method: 'DELETE' })]

    await user.click(await screen.findByRole('button', { name: 'Delete web-1' }))
    expect(fetchMock).not.toHaveBeenCalledWith(...deleteCall)

    await user.click(screen.getByRole('button', { name: 'Confirm deleting web-1' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(...deleteCall))
  })

  it('creates a resource from the form', async () => {
    const fetchMock = serve('operator', { 'POST /resources': { ...web, id: 'r3', name: 'api-1' } })
    renderWithClient(<Dashboard />)
    const user = userEvent.setup()

    await user.type(await screen.findByLabelText('Name'), 'api-1')
    await user.click(screen.getByRole('button', { name: 'Create' }))

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        '/resources',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'api-1', image: 'nginx:latest' }),
        }),
      ),
    )
  })

  it('shows admins the recent activity', async () => {
    serve('admin')
    renderWithClient(<Dashboard />)

    expect(await screen.findByText('created web-1')).toBeInTheDocument()
  })

  it('charts the selected resource, with a table view of the same readings', async () => {
    const history = [0, 1, 2].map((i) => ({
      collected_at: new Date(Date.now() - (2 - i) * 15_000).toISOString(),
      cpu_percent: 10 + i,
      memory_bytes: 200 * MiB,
    }))
    serve('viewer', { 'GET /resources/r1/metrics': history })
    renderWithClient(<Dashboard />)
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'web-1' }))
    expect(await screen.findByRole('img', { name: /CPU/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Memory/ })).toBeInTheDocument()

    await user.click(screen.getByLabelText('Table view'))
    const table = screen.getByRole('table', { name: /Readings/ })
    expect(within(table).getByText('12%')).toBeInTheDocument()
  })

  it('signs out', async () => {
    serve('viewer')
    renderWithClient(<Dashboard />)

    await userEvent.setup().click(await screen.findByRole('button', { name: 'Sign out' }))

    expect(getToken()).toBeNull()
  })
})
