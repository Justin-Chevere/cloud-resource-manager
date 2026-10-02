import type { ActualState, Resource } from './api.ts'

export type Tone = 'good' | 'warning' | 'critical' | 'neutral'

// A state is never shown by color alone: each has an icon and a word as well.
export const STATUS: Record<ActualState, { label: string; icon: string; tone: Tone }> = {
  running: { label: 'Running', icon: '✓', tone: 'good' },
  pending: { label: 'Pending', icon: '◷', tone: 'warning' },
  stopped: { label: 'Stopped', icon: '■', tone: 'neutral' },
  error: { label: 'Error', icon: '✕', tone: 'critical' },
}

// What the reconciler is about to do, while desired and actual state differ.
export function transition(resource: Resource): string | null {
  const { desired_state: desired, actual_state: actual } = resource
  if (desired === 'deleted') return 'deleting'
  if (actual === 'error') return 'retrying'
  if (desired === 'stopped' && actual === 'running') return 'stopping'
  if (desired === 'running' && actual === 'stopped') return 'starting'
  return null
}
