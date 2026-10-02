import type { Resource } from './api.ts'
import { STATUS, transition } from './status.ts'

export function StatusBadge({ resource }: { resource: Resource }) {
  const status = STATUS[resource.actual_state]
  const next = transition(resource)
  return (
    <span className="status">
      <span className={`status-icon tone-${status.tone}`} aria-hidden="true">
        {status.icon}
      </span>
      {status.label}
      {next && <span className="status-next"> · {next}</span>}
    </span>
  )
}
