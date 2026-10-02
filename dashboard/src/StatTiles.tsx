import type { LatestMetric, Resource } from './api.ts'
import { formatBytes, formatCores } from './format.ts'

interface Props {
  resources: Resource[]
  readings: Map<string, LatestMetric>
}

export function StatTiles({ resources, readings }: Props) {
  const running = resources.filter((resource) => resource.actual_state === 'running')
  const errors = resources.filter((resource) => resource.actual_state === 'error').length
  // Only running resources count: a stopped one keeps its last, stale reading.
  const live = running.flatMap((resource) => readings.get(resource.id) ?? [])
  const cpu = live.reduce((total, reading) => total + reading.cpu_percent, 0)
  const memory = live.reduce((total, reading) => total + reading.memory_bytes, 0)

  return (
    <section className="tiles" aria-label="Summary">
      <Tile label="Resources" value={String(resources.length)} />
      <Tile label="Running" value={String(running.length)} />
      <Tile label="Errors" value={String(errors)} alert={errors > 0} />
      <Tile label="CPU in use" value={formatCores(cpu)} />
      <Tile label="Memory in use" value={formatBytes(memory)} />
    </section>
  )
}

function Tile({ label, value, alert = false }: { label: string; value: string; alert?: boolean }) {
  return (
    <div className="tile">
      <span className="tile-label">{label}</span>
      <span className="tile-value">
        {alert && (
          <span className="status-icon tone-critical" aria-hidden="true">
            ✕
          </span>
        )}
        {value}
      </span>
    </div>
  )
}
