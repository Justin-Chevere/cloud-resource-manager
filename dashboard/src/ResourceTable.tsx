import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { deleteResource, setDesiredState } from './api.ts'
import type { LatestMetric, Resource } from './api.ts'
import { formatBytes, formatPercent } from './format.ts'
import { StatusBadge } from './StatusBadge.tsx'

interface Props {
  resources: Resource[]
  readings: Map<string, LatestMetric>
  loading: boolean
  canOperate: boolean
  selectedId: string | null
  onSelect: (id: string) => void
}

export function ResourceTable({ resources, readings, loading, canOperate, selectedId, onSelect }: Props) {
  return (
    <section className="card" aria-labelledby="resources-title">
      <h2 id="resources-title">Resources</h2>
      {resources.length === 0 ? (
        <p className="muted">{loading ? 'Loading…' : 'No resources yet.'}</p>
      ) : (
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Image</th>
                <th scope="col">Status</th>
                <th scope="col" className="num">
                  CPU
                </th>
                <th scope="col" className="num">
                  Memory
                </th>
                {canOperate && (
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {resources.map((resource) => (
                <Row
                  key={resource.id}
                  resource={resource}
                  reading={readings.get(resource.id)}
                  canOperate={canOperate}
                  selected={resource.id === selectedId}
                  onSelect={onSelect}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

interface RowProps {
  resource: Resource
  reading: LatestMetric | undefined
  canOperate: boolean
  selected: boolean
  onSelect: (id: string) => void
}

function Row({ resource, reading, canOperate, selected, onSelect }: RowProps) {
  // A stopped resource keeps its last reading; showing it as current would mislead.
  const live = resource.actual_state === 'running' ? reading : undefined
  return (
    <tr className={selected ? 'is-selected' : undefined}>
      <td>
        <button
          type="button"
          className="link"
          aria-pressed={selected}
          onClick={() => onSelect(resource.id)}
        >
          {resource.name}
        </button>
      </td>
      <td className="mono muted">{resource.image}</td>
      <td>
        <StatusBadge resource={resource} />
      </td>
      <td className="num">{live ? <CpuMeter percent={live.cpu_percent} /> : <NoReading />}</td>
      <td className="num">{live ? formatBytes(live.memory_bytes) : <NoReading />}</td>
      {canOperate && (
        <td>
          <Actions resource={resource} />
        </td>
      )}
    </tr>
  )
}

// A meter: one ratio against a limit (100% = one full core). The track is a
// lighter step of the same blue, so the whole bar reads as one measure.
function CpuMeter({ percent }: { percent: number }) {
  return (
    <span className="meter">
      <span className="meter-track" aria-hidden="true">
        <span className="meter-fill" style={{ width: `${Math.min(100, percent)}%` }} />
      </span>
      {formatPercent(percent)}
    </span>
  )
}

function NoReading() {
  return (
    <>
      <span aria-hidden="true">—</span>
      <span className="visually-hidden">No reading</span>
    </>
  )
}

function Actions({ resource }: { resource: Resource }) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['resources'] })
    void queryClient.invalidateQueries({ queryKey: ['audit'] })
  }
  const toggle = useMutation({
    mutationFn: (state: 'running' | 'stopped') => setDesiredState(resource.id, state),
    onSuccess: refresh,
  })
  const remove = useMutation({ mutationFn: () => deleteResource(resource.id), onSuccess: refresh })

  if (resource.desired_state === 'deleted') return <span className="muted">Deleting…</span>

  const busy = toggle.isPending || remove.isPending
  const error = toggle.error ?? remove.error
  const running = resource.desired_state === 'running'
  return (
    <div className="row-actions">
      {confirming ? (
        <>
          <button
            type="button"
            className="button button-small button-danger"
            disabled={busy}
            onClick={() => remove.mutate()}
            aria-label={`Confirm deleting ${resource.name}`}
          >
            Confirm
          </button>
          <button type="button" className="button button-small" onClick={() => setConfirming(false)}>
            Cancel
          </button>
        </>
      ) : (
        <>
          <button
            type="button"
            className="button button-small"
            disabled={busy}
            onClick={() => toggle.mutate(running ? 'stopped' : 'running')}
            aria-label={`${running ? 'Stop' : 'Start'} ${resource.name}`}
          >
            {running ? 'Stop' : 'Start'}
          </button>
          <button
            type="button"
            className="button button-small"
            disabled={busy}
            onClick={() => setConfirming(true)}
            aria-label={`Delete ${resource.name}`}
          >
            Delete
          </button>
        </>
      )}
      {error && (
        <span className="form-error" role="alert">
          {error.message}
        </span>
      )}
    </div>
  )
}
