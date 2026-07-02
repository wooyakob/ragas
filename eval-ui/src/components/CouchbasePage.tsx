import { useEffect, useState } from 'react'
import type { CouchbaseConfig, EvalResult } from '../types'
import { getExampleQueries, saveToCouchbase } from '../api/client'

interface Props {
  runId: string
  results: EvalResult[]
}

export default function CouchbasePage({ runId, results }: Props) {
  const [config, setConfig] = useState<CouchbaseConfig>({
    connection_string: 'couchbases://cb.example.cloud.couchbase.com',
    username: '',
    password: '',
    bucket_name: 'agent_evals',
    scope_name: '_default',
    collection_name: 'agent_evaluations',
  })
  const [queries, setQueries] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [saveResult, setSaveResult] = useState<{ written: number; total: number } | null>(null)
  const [error, setError] = useState('')
  const [activeQuery, setActiveQuery] = useState('')

  useEffect(() => {
    getExampleQueries().then((qs) => {
      setQueries(qs)
      const first = Object.keys(qs)[0]
      if (first) setActiveQuery(first)
    })
  }, [])

  function update(key: keyof CouchbaseConfig, val: string) {
    setConfig((c) => ({ ...c, [key]: val }))
  }

  async function handleSave() {
    if (!runId) {
      setError('No evaluation run available. Run an evaluation first.')
      return
    }
    setSaving(true)
    setError('')
    setSaveResult(null)
    try {
      const res = await saveToCouchbase(runId, config)
      setSaveResult(res)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const filledQuery =
    queries[activeQuery]
      ?.replace(/\{bucket\}/g, config.bucket_name || 'agent_evals')
      .replace(/\{scope\}/g, config.scope_name || '_default')
      .replace(/\{collection\}/g, config.collection_name || 'agent_evaluations') ?? ''

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Couchbase</h2>
        <p className="text-gray-400 mt-1">
          Save evaluation results to Couchbase and query them with SQL++.
        </p>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <h3 className="font-semibold text-gray-200">Connection Settings</h3>
        <div className="grid grid-cols-2 gap-4">
          {(
            [
              ['connection_string', 'Connection String', 'couchbases://…'],
              ['username', 'Username', ''],
              ['password', 'Password', ''],
              ['bucket_name', 'Bucket', 'agent_evals'],
              ['scope_name', 'Scope', '_default'],
              ['collection_name', 'Collection', 'agent_evaluations'],
            ] as [keyof CouchbaseConfig, string, string][]
          ).map(([key, label, placeholder]) => (
            <div key={key} className={key === 'connection_string' ? 'col-span-2' : ''}>
              <label className="text-xs text-gray-500 block mb-1">{label}</label>
              <input
                type={key === 'password' ? 'password' : 'text'}
                value={config[key]}
                onChange={(e) => update(key, e.target.value)}
                placeholder={placeholder}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 w-full font-mono"
              />
            </div>
          ))}
        </div>

        {error && <p className="text-red-400 text-sm">{error}</p>}
        {saveResult && (
          <p className="text-green-400 text-sm">
            Saved {saveResult.written}/{saveResult.total} documents to Couchbase.
          </p>
        )}

        <button
          onClick={handleSave}
          disabled={saving || !results.length}
          className="w-full bg-green-700 hover:bg-green-600 disabled:bg-gray-700 disabled:text-gray-500 text-white font-semibold py-3 rounded-xl transition-colors"
        >
          {saving
            ? 'Saving…'
            : results.length
              ? `Save ${results.length} Results to Couchbase`
              : 'Run an evaluation first'}
        </button>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
        <h3 className="font-semibold text-gray-200">Example SQL++ Queries</h3>
        <div className="flex flex-wrap gap-2">
          {Object.keys(queries).map((key) => (
            <button
              key={key}
              onClick={() => setActiveQuery(key)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                activeQuery === key
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {key.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
        {filledQuery && (
          <div className="relative">
            <pre className="bg-gray-950 border border-gray-800 rounded-lg p-4 text-xs text-green-300 overflow-x-auto font-mono">
              {filledQuery.trim()}
            </pre>
            <button
              onClick={() => navigator.clipboard.writeText(filledQuery.trim())}
              className="absolute top-2 right-2 text-xs text-gray-500 hover:text-gray-300 bg-gray-800 px-2 py-1 rounded"
            >
              copy
            </button>
          </div>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h3 className="font-semibold text-gray-200 mb-3">Document Schema</h3>
        <pre className="text-xs text-gray-400 font-mono leading-relaxed">{`{
  "id":           "eval_<uuid>",
  "type":         "agent_evaluation",
  "session_id":   "<uuid>",
  "span_name":    "weather_agent",
  "timestamp":    "2024-01-15T10:30:00Z",
  "metrics": {
    "tool_step_efficiency":        0.85,
    "agent_response_faithfulness": 1.0
  },
  "trace_summary": {
    "total_tool_calls": 3,
    "unique_tools":     ["search", "calculator"],
    "tool_sequence":    ["search", "search", "calculator"],
    "num_turns":        2
  },
  "metadata":      { ... },
  "sample_preview": [
    { "role": "human", "content": "What is the weather?" },
    { "role": "ai",    "content": "The weather is 72°F." }
  ]
}`}</pre>
      </div>
    </div>
  )
}
