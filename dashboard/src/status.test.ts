import { describe, expect, it } from 'vitest'
import type { Resource } from './api.ts'
import { transition } from './status.ts'

const base = { id: 'r1', name: 'web-1', image: 'nginx', created_at: '', updated_at: '' }

describe('transition', () => {
  it.each([
    ['running', 'running', null],
    ['running', 'pending', null],
    ['stopped', 'running', 'stopping'],
    ['running', 'stopped', 'starting'],
    ['running', 'error', 'retrying'],
    ['deleted', 'running', 'deleting'],
  ] as const)('desired %s, actual %s: %s', (desired, actual, expected) => {
    const resource: Resource = { ...base, desired_state: desired, actual_state: actual }
    expect(transition(resource)).toBe(expected)
  })
})
