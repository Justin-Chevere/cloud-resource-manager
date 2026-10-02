import { describe, expect, it } from 'vitest'
import {
  areaPath,
  linePath,
  linearScale,
  nearestIndex,
  niceStep,
  splitAtGaps,
  timeTicks,
  typicalGap,
  valueTicks,
} from './chart.ts'

describe('niceStep', () => {
  it('rounds up to 1, 2, 2.5 or 5 times a power of ten', () => {
    expect([0.7, 1.3, 2.2, 3, 7, 13, 240].map(niceStep)).toEqual([1, 2, 2.5, 5, 10, 20, 250])
  })
})

describe('valueTicks', () => {
  it('runs from zero to a round number at or above the maximum', () => {
    expect(valueTicks(38)).toEqual([0, 10, 20, 30, 40])
    expect(valueTicks(498)).toEqual([0, 200, 400, 600])
    expect(valueTicks(10)).toEqual([0, 2.5, 5, 7.5, 10])
  })
})

describe('timeTicks', () => {
  it('places a few evenly spaced times inside the range', () => {
    const start = Date.UTC(2026, 0, 1, 10, 7)
    for (const minutes of [15, 60, 360, 1440]) {
      const end = start + minutes * 60_000
      const ticks = timeTicks(start, end)

      expect(ticks.length).toBeGreaterThanOrEqual(2)
      expect(ticks.length).toBeLessThanOrEqual(6)
      expect(ticks.every((tick) => tick >= start && tick <= end)).toBe(true)
      expect(new Set(ticks.slice(1).map((tick, i) => tick - ticks[i])).size).toBe(1)
    }
  })
})

describe('nearestIndex', () => {
  it('finds the closest time, clamping at both ends', () => {
    const times = [0, 10, 20]
    expect(nearestIndex(times, 14)).toBe(1)
    expect(nearestIndex(times, 16)).toBe(2)
    expect(nearestIndex(times, -5)).toBe(0)
    expect(nearestIndex(times, 99)).toBe(2)
    expect(nearestIndex([], 5)).toBe(-1)
  })
})

describe('gaps', () => {
  const points = [0, 15, 30, 45, 300, 315].map((seconds) => ({ t: seconds * 1000, v: 1 }))

  it('measures the usual spacing between readings', () => {
    expect(typicalGap(points)).toBe(15_000)
  })

  it('splits the line where readings stopped', () => {
    expect(splitAtGaps(points, 45_000).map((run) => run.length)).toEqual([4, 2])
  })
})

describe('paths', () => {
  const x = linearScale([0, 10], [0, 100])
  const y = linearScale([0, 1], [50, 0])
  const points = [
    { t: 0, v: 0 },
    { t: 10, v: 1 },
  ]

  it('draws the line through each point', () => {
    expect(linePath(points, x, y)).toBe('M0.0,50.0L100.0,0.0')
  })

  it('closes the area down to the baseline', () => {
    expect(areaPath(points, x, y, 50)).toBe('M0.0,50.0L100.0,0.0L100.0,50L0.0,50Z')
  })
})
