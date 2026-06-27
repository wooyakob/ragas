import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { EvalResult } from '../types'

const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444']

interface Props {
  results: EvalResult[]
}

export default function MetricsChart({ results }: Props) {
  if (results.length === 0) return null

  const metricKeys = Object.keys(results[0].metrics)
  const avgData = metricKeys.map((key, i) => {
    const vals = results.map((r) => r.metrics[key]).filter((v) => v != null)
    const avg = vals.reduce((a, b) => a + b, 0) / (vals.length || 1)
    return {
      name: key.replace(/_/g, ' '),
      value: parseFloat((avg * 100).toFixed(1)),
      color: COLORS[i % COLORS.length],
    }
  })

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      <h3 className="font-semibold text-gray-200 mb-4">Average Metric Scores</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={avgData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} interval={0} />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: '#9ca3af', fontSize: 11 }}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            formatter={(value: number) => [`${value}%`, 'Score']}
            contentStyle={{
              background: '#1f2937',
              border: '1px solid #374151',
              borderRadius: 8,
            }}
            labelStyle={{ color: '#e5e7eb' }}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {avgData.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
