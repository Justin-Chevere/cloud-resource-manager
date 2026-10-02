import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { ActivityFeed } from './ActivityFeed.tsx'
import { getMe, latestMetrics, listResources } from './api.ts'
import type { LatestMetric } from './api.ts'
import { CreateResourceForm } from './CreateResourceForm.tsx'
import { ResourceDetail } from './ResourceDetail.tsx'
import { ResourceTable } from './ResourceTable.tsx'
import { setToken } from './session.ts'
import { StatTiles } from './StatTiles.tsx'

// Resources change as the reconciler works (a pass every 2 s by default), and new
// readings arrive every 15 s, so each view refreshes on its own schedule.
const RESOURCES_EVERY_MS = 2_000
const READINGS_EVERY_MS = 5_000

export function Dashboard() {
  const me = useQuery({ queryKey: ['me'], queryFn: getMe, refetchInterval: 60_000 })
  const resources = useQuery({
    queryKey: ['resources'],
    queryFn: listResources,
    refetchInterval: RESOURCES_EVERY_MS,
  })
  const latest = useQuery({
    queryKey: ['metrics', 'latest'],
    queryFn: latestMetrics,
    refetchInterval: READINGS_EVERY_MS,
  })
  const [selectedId, setSelectedId] = useState<string | null>(null)

  if (me.isError) {
    return (
      <p className="page-message" role="alert">
        Couldn't load your account: {me.error.message}
      </p>
    )
  }
  if (!me.data) return <p className="page-message">Loading…</p>

  const { username, role } = me.data
  // The server enforces roles on every request; hiding controls a user can't use
  // just keeps the page honest about what they can do.
  const canOperate = role !== 'viewer'
  const list = resources.data ?? []
  const readings = new Map<string, LatestMetric>(
    (latest.data ?? []).map((reading) => [reading.resource_id, reading]),
  )
  const selected = list.find((resource) => resource.id === selectedId)

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">cloud-resource-manager</span>
        <span className="account">
          {username}
          <span className="role">{role}</span>
        </span>
        <button type="button" className="button" onClick={() => setToken(null)}>
          Sign out
        </button>
      </header>
      <main className="content">
        {resources.isError && (
          <p className="form-error" role="alert">
            Couldn't load resources: {resources.error.message}
          </p>
        )}
        <StatTiles resources={list} readings={readings} />
        {canOperate && <CreateResourceForm onCreated={setSelectedId} />}
        <ResourceTable
          resources={list}
          readings={readings}
          loading={resources.isPending}
          canOperate={canOperate}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        {selected && <ResourceDetail resource={selected} />}
        {role === 'admin' && <ActivityFeed resources={list} />}
      </main>
    </div>
  )
}
