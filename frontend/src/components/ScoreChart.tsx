import { useId } from 'react'
import type { MeasureTrend } from '../api/types'
import './ScoreChart.css'

/**
 * The Clinical Dashboard's score trend graph.
 *
 * The CTMS plots scores against "Weeks in Treatment (0 = First BH Contact)"
 * rather than calendar dates, which keeps episodes comparable — that's the
 * x-axis here too, with week 0 anchored on the caller-supplied first-contact
 * date (falling back to the series' own first score).
 *
 * The y-domain comes from the data plus headroom, NOT from a hardcoded
 * per-scale maximum: PHQ-9's 27 and GAD-7's 21 are well known, but the
 * pediatric scales' maxima aren't documented anywhere in our source
 * material, and inventing them is exactly what CLAUDE.md prohibits. The
 * remission reference line is drawn only for measures whose threshold is
 * confirmed (PHQ-9 and GAD-7, both < 5).
 */

const REMISSION_THRESHOLDS: Partial<Record<MeasureTrend['measure_type'], number>> = {
  PHQ9: 5,
  GAD7: 5,
}

const WIDTH = 560
const HEIGHT = 190
const PAD = { top: 12, right: 16, bottom: 34, left: 34 }

function weeksBetween(fromIso: string, toIso: string): number {
  const [fy, fm, fd] = fromIso.split('-').map(Number)
  const [ty, tm, td] = toIso.split('-').map(Number)
  const days =
    (Date.UTC(ty, tm - 1, td) - Date.UTC(fy, fm - 1, fd)) / 86_400_000
  return Math.max(0, Math.round((days / 7) * 10) / 10)
}

export function ScoreChart({
  trend,
  firstContactDate,
}: {
  trend: MeasureTrend
  firstContactDate: string | null
}) {
  const gradientId = useId()
  const points = trend.scores
  if (points.length === 0) {
    return (
      <div className="score-chart__empty">
        No {trend.measure_type} scores recorded in this episode yet.
      </div>
    )
  }

  const anchor = firstContactDate ?? points[0].score_date
  const xs = points.map((p) => weeksBetween(anchor, p.score_date))
  const ys = points.map((p) => p.score_value)

  const threshold = REMISSION_THRESHOLDS[trend.measure_type]
  const yMaxData = Math.max(...ys, threshold ?? 0)
  // Round the top of the scale up to a clean multiple of 5 with headroom.
  const yMax = Math.max(5, Math.ceil((yMaxData + 1) / 5) * 5)
  const xMax = Math.max(...xs, 4)

  const plotW = WIDTH - PAD.left - PAD.right
  const plotH = HEIGHT - PAD.top - PAD.bottom
  const sx = (weeks: number) => PAD.left + (xMax === 0 ? 0 : (weeks / xMax) * plotW)
  const sy = (score: number) => PAD.top + plotH - (score / yMax) * plotH

  const path = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${sx(xs[i]).toFixed(1)} ${sy(p.score_value).toFixed(1)}`)
    .join(' ')
  const areaPath =
    points.length > 1
      ? `${path} L ${sx(xs[xs.length - 1]).toFixed(1)} ${(PAD.top + plotH).toFixed(1)} L ${sx(xs[0]).toFixed(1)} ${(PAD.top + plotH).toFixed(1)} Z`
      : ''

  const yTicks = Array.from({ length: yMax / 5 + 1 }, (_, i) => i * 5)
  const xTickStep = xMax <= 8 ? 2 : xMax <= 20 ? 4 : Math.ceil(xMax / 6)
  const xTicks: number[] = []
  for (let w = 0; w <= xMax; w += xTickStep) xTicks.push(w)

  return (
    <figure className="score-chart">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="score-chart__svg"
        role="img"
        aria-label={`${trend.measure_type} scores over ${xMax} weeks in treatment, from ${ys[0]} to ${ys[ys.length - 1]}`}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--nf-secondary-light)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--nf-secondary-light)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {yTicks.map((tick) => (
          <g key={tick}>
            <line
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={sy(tick)}
              y2={sy(tick)}
              className="score-chart__grid"
            />
            <text x={PAD.left - 6} y={sy(tick) + 3} className="score-chart__tick" textAnchor="end">
              {tick}
            </text>
          </g>
        ))}

        {threshold !== undefined && (
          <g>
            <line
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={sy(threshold)}
              y2={sy(threshold)}
              className="score-chart__threshold"
            />
            <text
              x={WIDTH - PAD.right}
              y={sy(threshold) - 4}
              className="score-chart__threshold-label"
              textAnchor="end"
            >
              remission &lt; {threshold}
            </text>
          </g>
        )}

        {xTicks.map((tick) => (
          <text
            key={tick}
            x={sx(tick)}
            y={HEIGHT - PAD.bottom + 16}
            className="score-chart__tick"
            textAnchor="middle"
          >
            {tick}
          </text>
        ))}
        <text
          x={PAD.left + plotW / 2}
          y={HEIGHT - 4}
          className="score-chart__axis-label"
          textAnchor="middle"
        >
          Weeks in treatment (0 = first BH contact)
        </text>

        {areaPath && <path d={areaPath} fill={`url(#${gradientId})`} />}
        <path d={path} className="score-chart__line" />
        {points.map((p, i) => (
          <circle key={p.score_date + i} cx={sx(xs[i])} cy={sy(p.score_value)} r="3.5" className="score-chart__point">
            <title>
              {p.score_value} on {p.score_date} (week {xs[i]})
            </title>
          </circle>
        ))}
      </svg>
    </figure>
  )
}
