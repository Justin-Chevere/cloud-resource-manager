import { describe, expect, it } from 'vitest'
import { formatBytes, formatCores, formatPercent, MiB, timeAgo } from './format.ts'

describe('format', () => {
  it('shows memory in MiB, or GiB once it gets large', () => {
    expect(formatBytes(248 * MiB)).toBe('248 MiB')
    expect(formatBytes(1536 * MiB)).toBe('1.5 GiB')
  })

  it('shows percentages with at most one decimal', () => {
    expect(formatPercent(12.34)).toBe('12.3%')
    expect(formatPercent(10)).toBe('10%')
  })

  it('shows total CPU in cores', () => {
    expect(formatCores(250)).toBe('2.50 cores')
  })

  it('says how long ago something happened', () => {
    const then = '2026-01-01T00:00:00Z'
    const after = (seconds: number) => Date.parse(then) + seconds * 1000
    expect(timeAgo(then, after(42))).toBe('42s ago')
    expect(timeAgo(then, after(5 * 60))).toBe('5 min ago')
    expect(timeAgo(then, after(3 * 3600))).toBe('3 h ago')
    expect(timeAgo(then, after(2 * 86400))).toBe('2 d ago')
  })
})
