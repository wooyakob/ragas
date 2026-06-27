import type { Dispatch, SetStateAction } from 'react'
import type { Page } from '../App'
import type { EvalResult } from '../types'

interface Props {
  setPage: Dispatch<SetStateAction<Page>>
  lastResults: EvalResult[]
}

export default function Dashboard({ setPage, lastResults }: Props) {
  const avgMetrics: Record<string, number> = {}

  if (lastResults.length > 0) {
    for (const k of Object.keys(lastResults[0].metrics)) {
      const vals = lastResults.map((r) => r.metrics[k]).filter((v) => v != null)
      avgMetrics[k] = vals.reduce((a, b) => a + b, 0) / vals.length
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Dashboard</h2>
        <p className="text-gray-400 mt-1">
          Evaluate agent traces from Agent Catalog with Ragas metrics.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Sessions Evaluated" value={lastResults.length} color="blue" />
        <StatCard label="Metrics Computed" value={Object.keys(avgMetrics).length} color="purple" />
        <StatCard
          label="Avg Faithfulness"
          value={
            avgMetrics['agent_response_faithfulness'] != null
              ? `${(avgMetrics['agent_response_faithfulness'] * 100).toFixed(0)}%`
              : '—'
          }
          color="green"
        />
      </div>

      {lastResults.length > 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h3 className="font-semibold text-gray-200 mb-4">Average Scores</h3>
          <div className="space-y-3">
            {Object.entries(avgMetrics).map(([key, val]) => (
              <div key={key}>
                <div className="flex justify-between text-sm text-gray-400 mb-1">
                  <span>{key.replace(/_/g, ' ')}</span>
                  <span>{(val * 100).toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full"
                    style={{ width: `${Math.min(val * 100, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {lastResults.length === 0 && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <h3 className="font-semibold text-gray-200 mb-3">Quick Start</h3>
          <ol className="space-y-3 text-sm text-gray-400">
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center">
                1
              </span>
              <span>
                Go to{' '}
                <button className="text-blue-400 hover:underline" onClick={() => setPage('evaluate')}>
                  Evaluate
                </button>{' '}
                and upload an agentc JSONL activity log.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center">
                2
              </span>
              <span>Select metrics and run the evaluation.</span>
            </li>
            <li className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-600 text-white text-xs flex items-center justify-center">
                3
              </span>
              <span>
                Optionally save results to{' '}
                <button className="text-blue-400 hover:underline" onClick={() => setPage('couchbase')}>
                  Couchbase
                </button>{' '}
                for SQL++ analysis.
              </span>
            </li>
          </ol>
        </div>
      )}
    </div>
  )
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string
  value: string | number
  color: 'blue' | 'purple' | 'green'
}) {
  const colors = { blue: 'text-blue-400', purple: 'text-purple-400', green: 'text-green-400' }
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-5">
      <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      <p className={`text-3xl font-bold mt-2 ${colors[color]}`}>{value}</p>
    </div>
  )
}
