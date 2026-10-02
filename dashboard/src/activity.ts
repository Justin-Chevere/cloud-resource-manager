import type { AuditEvent } from './api.ts'

interface Change {
  from: unknown
  to: unknown
}

function asChange(value: unknown): Change | null {
  return typeof value === 'object' && value !== null && 'to' in value ? (value as Change) : null
}

// A short sentence for an audit event, e.g. "set web-1 to stopped".
export function describeEvent(event: AuditEvent, names: Map<string, string>): string {
  const { details } = event
  const name = typeof details.name === 'string' ? details.name : names.get(event.target_id)
  const resource = name ?? 'a resource'
  switch (event.action) {
    case 'resource.create':
      return `created ${resource}`
    case 'resource.update': {
      const state = asChange(details.desired_state)
      return state ? `set ${resource} to ${String(state.to)}` : `changed ${resource}`
    }
    case 'resource.delete':
      return `deleted ${resource}`
    case 'user.create':
      return `added ${String(details.username)} as ${String(details.role)}`
    case 'user.update': {
      const active = asChange(details.is_active)
      const role = asChange(details.role)
      if (active) return active.to ? 'reactivated a user' : 'deactivated a user'
      if (role) return `changed a user's role to ${String(role.to)}`
      return 'updated a user'
    }
    case 'password_reset.issue':
      return 'issued a password reset'
    case 'password_reset.complete':
      return 'reset their password'
    default:
      return event.action
  }
}
