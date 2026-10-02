import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Point } from './chart.ts'
import { LineChart } from './LineChart.tsx'

function renderChart(points: Point[]) {
  const end = points[points.length - 1].t
  return render(
    <LineChart
      title="CPU"
      points={points}
      start={0}
      end={end}
      formatValue={(value) => `${value}%`}
      minTop={10}
    />,
  )
}

const points = [
  { t: 0, v: 10 },
  { t: 60_000, v: 30 },
  { t: 120_000, v: 20 },
]

describe('LineChart', () => {
  it('labels the newest value at the end of the line', () => {
    renderChart(points)
    expect(screen.getByText('20%', { selector: 'text.chart-end-label' })).toBeInTheDocument()
  })

  it('reads out values from the keyboard', async () => {
    renderChart(points)
    const user = userEvent.setup()

    await user.tab()
    expect(screen.getByRole('img', { name: /CPU/ })).toHaveFocus()
    expect(screen.getByRole('status')).toHaveTextContent(/^20% at/)

    await user.keyboard('{ArrowLeft}')
    expect(screen.getByRole('status')).toHaveTextContent(/^30% at/)

    await user.keyboard('{Home}')
    expect(screen.getByRole('status')).toHaveTextContent(/^10% at/)
  })

  it('leaves a gap where readings stopped, instead of drawing through it', () => {
    const { container } = renderChart(
      [0, 15, 30, 600, 615].map((seconds) => ({ t: seconds * 1000, v: 5 })),
    )
    expect(container.querySelectorAll('path.chart-line')).toHaveLength(2)
  })
})
