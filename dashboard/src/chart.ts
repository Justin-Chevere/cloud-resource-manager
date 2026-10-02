// The math behind LineChart, kept free of React so it is easy to test.

export interface Point {
  t: number // time, in ms since the epoch
  v: number
}

type Scale = (value: number) => number

// Maps a value range onto a pixel range, e.g. 0-100% onto 180-12 px.
export function linearScale([d0, d1]: [number, number], [r0, r1]: [number, number]): Scale {
  const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0)
  return (value) => r0 + (value - d0) * k
}

// A step a reader can add up at a glance: 1, 2, 2.5 or 5 times a power of ten.
export function niceStep(raw: number): number {
  if (!(raw > 0)) return 1
  const power = 10 ** Math.floor(Math.log10(raw))
  const factor = [1, 2, 2.5, 5, 10].find((f) => f * power >= raw) ?? 10
  return factor * power
}

// Axis ticks from zero up to a round number at or above `max`.
export function valueTicks(max: number, count = 4): number[] {
  const step = niceStep(max / count)
  const steps = Math.max(1, Math.ceil(max / step))
  return Array.from({ length: steps + 1 }, (_, i) => Number((i * step).toPrecision(12)))
}

const MINUTE = 60_000
const TIME_STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 180, 360, 720].map((m) => m * MINUTE)

// At most `maxTicks` round times (local clock) between start and end.
export function timeTicks(start: number, end: number, maxTicks = 6): number[] {
  const step =
    TIME_STEPS.find((s) => Math.floor((end - start) / s) + 1 <= maxTicks) ??
    TIME_STEPS[TIME_STEPS.length - 1]
  // Align to the local clock, so "every 15 minutes" lands on :00, :15, :30 and :45.
  const offset = -new Date(start).getTimezoneOffset() * MINUTE
  const ticks: number[] = []
  for (let t = Math.ceil((start + offset) / step) * step - offset; t <= end; t += step) {
    ticks.push(t)
  }
  return ticks
}

// Index of the time closest to `time` in a sorted list, or -1 if the list is empty.
export function nearestIndex(times: number[], time: number): number {
  if (times.length === 0) return -1
  let lo = 0
  let hi = times.length - 1
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (times[mid] < time) lo = mid + 1
    else hi = mid
  }
  return lo > 0 && time - times[lo - 1] < times[lo] - time ? lo - 1 : lo
}

// The usual time between readings (the median), so a missing stretch stands out.
export function typicalGap(points: Point[]): number {
  if (points.length < 2) return Infinity
  const gaps = points
    .slice(1)
    .map((point, i) => point.t - points[i].t)
    .sort((a, b) => a - b)
  return gaps[Math.floor(gaps.length / 2)]
}

// Splits the series wherever readings stop for longer than `maxGap` (the resource
// was stopped), so the chart shows a gap instead of a line through invented data.
export function splitAtGaps(points: Point[], maxGap: number): Point[][] {
  const runs: Point[][] = []
  for (const point of points) {
    const run = runs[runs.length - 1]
    if (run && point.t - run[run.length - 1].t <= maxGap) run.push(point)
    else runs.push([point])
  }
  return runs
}

export function linePath(points: Point[], x: Scale, y: Scale): string {
  return points
    .map((point, i) => `${i === 0 ? 'M' : 'L'}${x(point.t).toFixed(1)},${y(point.v).toFixed(1)}`)
    .join('')
}

// The line, closed down to the baseline, for the soft fill underneath it.
export function areaPath(points: Point[], x: Scale, y: Scale, baseline: number): string {
  if (points.length === 0) return ''
  const first = x(points[0].t).toFixed(1)
  const last = x(points[points.length - 1].t).toFixed(1)
  return `${linePath(points, x, y)}L${last},${baseline}L${first},${baseline}Z`
}
