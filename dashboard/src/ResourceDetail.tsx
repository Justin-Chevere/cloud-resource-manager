import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { resourceMetrics } from './api.ts'
import type { MetricPoint, Resource } from './api.ts'
import { formatBytes, formatClock, formatPercent, MiB } from './format.ts'
import { LineChart } from './LineChart.tsx'
import { StatusBadge } from './StatusBadge.tsx'

const RANGES = [
  { minutes: 15, label: '15 min' },
  { minutes: 60, label: '1 hour' },
  { minutes: 360, label: '6 hours' },
  { minutes: 1440, label: '24 hours' },
]
const MAX_TABLE_ROWS = 500

export function ResourceDetail({ resource }: { resource: Resource }) {
  const [minutes, setMinutes] = useState(60)
  const [asTable, setAsTable] = useState(false)
  const history = useQuery({
    queryKey: ['metrics', resource.id, minutes],
    // The charts end at the moment the readings were fetched. Recording it here,
    // rather than reading the clock while rendering, keeps every render identical.
    queryFn: async () => ({
      samples: await resourceMetrics(resource.id, minutes),
      fetchedAt: Date.now(),
    }),
    refetchInterval: 15_000,
    // Changing the range keeps the old charts up, dimmed, until the new data
    // arrives, instead of flashing an empty frame.
    placeholderData: keepPreviousData,
  })

  const end = history.data?.fetchedAt ?? 0
  const start = end - minutes * 60_000
  const samples = (history.data?.samples ?? []).filter(
    (sample) => Date.parse(sample.collected_at) >= start,
  )
  const cpu = samples.map((sample) => ({ t: Date.parse(sample.collected_at), v: sample.cpu_percent }))
  const memory = samples.map((sample) => ({
    t: Date.parse(sample.collected_at),
    v: sample.memory_bytes / MiB,
  }))

  return (
    <section className="card" aria-labelledby="detail-title">
      <div className="detail-head">
        <h2 id="detail-title">{resource.name}</h2>
        <StatusBadge resource={resource} />
        <span className="mono muted">{resource.image}</span>
      </div>
      {/* One row of filters, above everything it scopes. */}
      <div className="filters">
        <div className="chips" role="group" aria-label="Time range">
          {RANGES.map((range) => (
            <button
              key={range.minutes}
              type="button"
              className="chip"
              aria-pressed={range.minutes === minutes}
              onClick={() => setMinutes(range.minutes)}
            >
              {range.label}
            </button>
          ))}
        </div>
        <label className="toggle">
          <input type="checkbox" checked={asTable} onChange={(event) => setAsTable(event.target.checked)} />
          Table view
        </label>
      </div>
      <div className={history.isPlaceholderData ? 'is-refreshing' : undefined}>
        {samples.length === 0 ? (
          <p className="muted empty">{emptyMessage(resource, history.isPending)}</p>
        ) : asTable ? (
          <ReadingsTable samples={samples} />
        ) : (
          // CPU and memory are different units, so they get two charts, never
          // one chart with two scales.
          <div className="charts">
            <LineChart
              title="CPU, % of one core"
              points={cpu}
              start={start}
              end={end}
              formatValue={formatPercent}
              minTop={10}
            />
            <LineChart
              title="Memory"
              points={memory}
              start={start}
              end={end}
              formatValue={(mib) => formatBytes(mib * MiB)}
              minTop={64}
            />
          </div>
        )}
      </div>
    </section>
  )
}

function emptyMessage(resource: Resource, loading: boolean): string {
  if (loading) return 'Loading readings…'
  if (resource.actual_state !== 'running') return 'Not running, so there is nothing to measure.'
  return 'No readings yet. The first one arrives within about 15 seconds.'
}

// The table twin of the charts: every value, readable without hovering.
function ReadingsTable({ samples }: { samples: MetricPoint[] }) {
  const rows = samples.slice(-MAX_TABLE_ROWS).reverse()
  return (
    <div className="table-scroll readings">
      <table className="table">
        <caption className="visually-hidden">Readings, newest first</caption>
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col" className="num">
              CPU
            </th>
            <th scope="col" className="num">
              Memory
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((sample) => (
            <tr key={sample.collected_at}>
              <td>{formatClock(Date.parse(sample.collected_at))}</td>
              <td className="num">{formatPercent(sample.cpu_percent)}</td>
              <td className="num">{formatBytes(sample.memory_bytes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {samples.length > MAX_TABLE_ROWS && (
        <p className="muted">
          Showing the newest {MAX_TABLE_ROWS} of {samples.length} readings.
        </p>
      )}
    </div>
  )
}
