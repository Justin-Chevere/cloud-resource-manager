import { useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent, PointerEvent, RefObject } from 'react'
import {
  areaPath,
  linePath,
  linearScale,
  nearestIndex,
  splitAtGaps,
  timeTicks,
  typicalGap,
  valueTicks,
} from './chart.ts'
import type { Point } from './chart.ts'
import { formatClock } from './format.ts'

// Includes the band for the time labels, so the card never needs its own scrollbar.
const HEIGHT = 220
const MARGIN = { top: 16, right: 72, bottom: 28, left: 64 }

interface Props {
  title: string
  points: Point[]
  start: number
  end: number
  formatValue: (value: number) => string
  // The y axis never tops out below this, so a nearly idle resource isn't
  // stretched across the whole height to look busy.
  minTop: number
}

export function LineChart({ title, points, start, end, formatValue, minTop }: Props) {
  const plotRef = useRef<HTMLDivElement>(null)
  const width = useWidth(plotRef)
  const [active, setActive] = useState<number | null>(null)

  const left = MARGIN.left
  const right = Math.max(left + 1, width - MARGIN.right)
  const top = MARGIN.top
  const bottom = HEIGHT - MARGIN.bottom

  const yTicks = valueTicks(Math.max(minTop, ...points.map((point) => point.v)))
  const x = linearScale([start, end], [left, right])
  const y = linearScale([0, yTicks[yTicks.length - 1]], [bottom, top])
  const runs = splitAtGaps(points, typicalGap(points) * 3)
  const last = points[points.length - 1]
  const shown = active === null ? undefined : points[active]

  // The crosshair snaps to the reading nearest the pointer, so nobody has to
  // land exactly on a 2px line.
  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (points.length === 0) return
    const bounds = event.currentTarget.getBoundingClientRect()
    const time = start + ((event.clientX - bounds.left - left) / (right - left)) * (end - start)
    setActive(nearestIndex(points.map((point) => point.t), time))
  }

  // The same readout from the keyboard: arrows step through readings.
  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    const lastIndex = points.length - 1
    if (lastIndex < 0) return
    if (event.key === 'ArrowLeft') setActive((i) => Math.max(0, (i ?? lastIndex + 1) - 1))
    else if (event.key === 'ArrowRight') setActive((i) => Math.min(lastIndex, (i ?? lastIndex) + 1))
    else if (event.key === 'Home') setActive(0)
    else if (event.key === 'End') setActive(lastIndex)
    else if (event.key === 'Escape') setActive(null)
    else return
    event.preventDefault()
  }

  return (
    <figure className="chart">
      <figcaption className="chart-title">{title}</figcaption>
      <div className="chart-plot" ref={plotRef}>
        <svg
          width={width}
          height={HEIGHT}
          role="img"
          aria-label={`${title}. Use the left and right arrow keys to read values.`}
          tabIndex={0}
          onPointerMove={onPointerMove}
          onPointerLeave={() => setActive(null)}
          onFocus={() => setActive(points.length > 0 ? points.length - 1 : null)}
          onBlur={() => setActive(null)}
          onKeyDown={onKeyDown}
        >
          {yTicks.map((tick) => (
            <g key={tick}>
              <line
                className={tick === 0 ? 'chart-baseline' : 'chart-grid'}
                x1={left}
                x2={right}
                y1={y(tick)}
                y2={y(tick)}
              />
              <text className="chart-tick" x={left - 8} y={y(tick)} dy="0.32em" textAnchor="end">
                {formatValue(tick)}
              </text>
            </g>
          ))}
          {timeTicks(start, end).map((tick) => (
            <text key={tick} className="chart-tick" x={x(tick)} y={HEIGHT - 6} textAnchor="middle">
              {formatClock(tick, false)}
            </text>
          ))}
          {runs.map((run) => (
            <g key={run[0].t}>
              <path className="chart-area" d={areaPath(run, x, y, bottom)} />
              <path className="chart-line" d={linePath(run, x, y)} />
            </g>
          ))}
          {last && (
            <>
              <circle className="chart-dot" cx={x(last.t)} cy={y(last.v)} r={4} />
              <text className="chart-end-label" x={x(last.t) + 10} y={y(last.v)} dy="0.32em">
                {formatValue(last.v)}
              </text>
            </>
          )}
          {shown && (
            <>
              <line className="chart-crosshair" x1={x(shown.t)} x2={x(shown.t)} y1={top} y2={bottom} />
              <circle className="chart-dot" cx={x(shown.t)} cy={y(shown.v)} r={4} />
            </>
          )}
        </svg>
        {shown && (
          <div
            className="chart-tooltip"
            style={{ left: Math.min(Math.max(x(shown.t), 72), width - 72), top: y(shown.v) }}
            aria-hidden="true"
          >
            <strong>
              <span className="chart-key" />
              {formatValue(shown.v)}
            </strong>
            <span>{formatClock(shown.t)}</span>
          </div>
        )}
        <div className="visually-hidden" role="status">
          {shown ? `${formatValue(shown.v)} at ${formatClock(shown.t)}` : ''}
        </div>
      </div>
    </figure>
  )
}

// Tracks the element's width, so the chart redraws to fit when the page resizes.
function useWidth(ref: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(640)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    if (element.clientWidth > 0) setWidth(element.clientWidth)
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)))
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref])
  return width
}
