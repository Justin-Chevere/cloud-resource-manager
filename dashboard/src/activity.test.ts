import { describe, expect, it } from 'vitest'
import { describeEvent } from './activity.ts'
import type { AuditEvent } from './api.ts'

function event(action: string, details: Record<string, unknown> = {}): AuditEvent {
  return { id: 1, created_at: '', actor: 'admin', action, target_id: 'r1', details }
}

const names = new Map([['r1', 'web-1']])
const stopped = { desired_state: { from: 'running', to: 'stopped' } }

describe('describeEvent', () => {
  it('describes resource changes by name', () => {
    expect(describeEvent(event('resource.create', { name: 'web-1' }), new Map())).toBe('created web-1')
    expect(describeEvent(event('resource.update', stopped), names)).toBe('set web-1 to stopped')
    expect(describeEvent(event('resource.delete', { name: 'web-1' }), new Map())).toBe('deleted web-1')
  })

  it('still reads well once the resource is gone', () => {
    expect(describeEvent(event('resource.update', stopped), new Map())).toBe(
      'set a resource to stopped',
    )
  })

  it('describes user and password events', () => {
    const role = { role: { from: 'viewer', to: 'operator' } }
    expect(describeEvent(event('user.create', { username: 'bob', role: 'viewer' }), names)).toBe(
      'added bob as viewer',
    )
    expect(describeEvent(event('user.update', role), names)).toBe("changed a user's role to operator")
    expect(describeEvent(event('user.update', { is_active: { from: true, to: false } }), names)).toBe(
      'deactivated a user',
    )
    expect(describeEvent(event('password_reset.complete'), names)).toBe('reset their password')
  })
})
