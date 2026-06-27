import { useEffect, useRef, useState } from 'react'
import type { AvailableMetric, EvalResult, ParseResponse } from '../types'
import { getAvailableMetrics, parseTraces, runEvaluation } from '../api/client'
import MetricsChart from './MetricsChart'
import TraceViewer from './TraceViewer'

interface Props {
  onResults: (runId: string, results: EvalResult[]) => void
}

type Step = 'upload' | 'configure' | 'results'

export default function EvaluatePage({ onResults }: Props) {
  const [step, setStep] = useState<Step>('upload')
  const [parseResponse, setParseResponse] = useState<ParseResponse | null>(null)
  const [availableMetrics, setAvailableMetrics] = useState<AvailableMetric[]>([])
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([
    'tool_step_efficiency',
    'agent_response_faithfulness',
  ])
  const [llmModel, setLlmModel] = useState('gpt-4o-mini')
  const [openAIKey, setOpenAIKey] = useState('')
  const [results, setResults] = useState<EvalResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [viewingTrace, setViewingTrace] = useState<EvalResult | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    getAvailableMetrics().then(setAvailableMetrics).catch(() => {})
  }, [])

  async function handleFile(file: File) {
    setLoading(true)
    setError('')
    try {
      const resp = await parseTraces(file)
      setParseResponse(resp)
      setStep('configure')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  function toggleMetric(id: string) {
    setSelectedMetrics((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id],
    )
  }

  async function handleEvaluate() {
    if (!parseResponse) return
    setLoading(true)
    setError('')
    try {
      const resp = await runEvaluation(
        parseResponse.run_id,
        selectedMetrics,
        llmModel,
        openAIKey || undefined,
      )
      setResults(resp.results)
      onResults(resp.run_id, resp.results)
      setStep('results')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Evaluate</h2>
        <p className="text-gray-400 mt-1">Upload agentc traces and compute Ragas metrics.</p>
      </div>

      {/* Step indicator */}
      <div className="flex gap-2 items-center text-sm">
        {(['upload', 'configure', 'results'] as Step[]).map((s, i) => (
          <span key={s} className="flex items-center gap-2">
            {i > 0 && <span className="text-gray-700">›</span>}
            <span
              className={`px-3 py-1 rounded-full ${
                step === s
                  ? 'bg-blue-600 text-white'
                  : step === 'results' || (step === 'configure' && s === 'upload')
                    ? 'bg-gray-700 text-gray-300'
                    : 'text-gray-600'
              }`}
            >
              {s}
            </span>
          </span>
        ))}
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-700 rounded-lg p-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Upload step */}
      {step === 'upload' && (
        <div
          className="border-2 border-dashed border-gray-700 rounded-2xl p-12 text-center cursor-pointer hover:border-blue-500 transition-colors"
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault()
            const f = e.dataTransfer.files[0]
            if (f) handleFile(f)
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".jsonl,.json,.log"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) handleFile(f)
            }}
          />
          <p className="text-4xl mb-3">\u{1F4C2}</p>
          {loading ? (
            <p className="text-gray-400">Parsing traces…</p>
          ) : (
            <>
              <p className="text-gray-300 font-medium">Drop agentc JSONL file here</p>
              <p className="text-gray-500 text-sm mt-1">or click to browse</p>
            </>
          )}
        </div>
      )}

      {/* Configure step */}
      {step === 'configure' && parseResponse && (
        <div className="space-y-5">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h3 className="font-semibold text-gray-200 mb-1">Parsed Sessions</h3>
            <p className="text-gray-400 text-sm">
              Found{' '}
              <span className="text-blue-400 font-bold">{parseResponse.session_count}</span>{' '}
              sessions ready for evaluation.
            </p>
            <div className="mt-3 space-y-2 max-h-48 overflow-y-auto">
              {parseResponse.sessions.map((s) => (
                <div
                  key={s.session_id}
                  className="flex items-center justify-between bg-gray-800 rounded-lg px-3 py-2 text-sm"
                >
                  <span className="text-gray-300 font-mono text-xs">{s.session_id.slice(0, 12)}…</span>
                  <span className="text-gray-400">{s.span_name}</span>
                  <span className="text-gray-500">{s.message_count} msgs</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h3 className="font-semibold text-gray-200 mb-3">Select Metrics</h3>
            <div className="space-y-3">
              {availableMetrics.map((m) => (
                <label key={m.id} className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedMetrics.includes(m.id)}
                    onChange={() => toggleMetric(m.id)}
                    className="mt-1 accent-blue-500"
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-200">
                      {m.name}
                      {m.requires_reference && (
                        <span className="ml-2 text-xs bg-yellow-900 text-yellow-300 px-1.5 py-0.5 rounded">
                          needs reference
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">{m.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
            <h3 className="font-semibold text-gray-200">LLM Settings</h3>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Model (for faithfulness metric)</label>
              <select
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 w-full"
              >
                <option value="gpt-4o-mini">gpt-4o-mini</option>
                <option value="gpt-4o">gpt-4o</option>
                <option value="gpt-4-turbo">gpt-4-turbo</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">
                OpenAI API Key (optional if set via env)
              </label>
              <input
                type="password"
                value={openAIKey}
                onChange={(e) => setOpenAIKey(e.target.value)}
                placeholder="sk-…"
                className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 w-full font-mono"
              />
            </div>
          </div>

          <button
            onClick={handleEvaluate}
            disabled={loading || selectedMetrics.length === 0}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-semibold py-3 rounded-xl transition-colors"
          >
            {loading ? 'Running evaluation…' : 'Run Evaluation'}
          </button>
        </div>
      )}

      {/* Results step */}
      {step === 'results' && results.length > 0 && (
        <div className="space-y-5">
          <MetricsChart results={results} />

          <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-800">
                <tr>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Session</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Agent</th>
                  {Object.keys(results[0].metrics).map((k) => (
                    <th key={k} className="text-right px-4 py-3 text-gray-400 font-medium">
                      {k.replace(/_/g, ' ')}
                    </th>
                  ))}
                  <th className="text-right px-4 py-3 text-gray-400 font-medium">Tools</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {results.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-800/50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-gray-400">
                      {r.session_id.slice(0, 8)}…
                    </td>
                    <td className="px-4 py-3 text-gray-300">{r.span_name}</td>
                    {Object.values(r.metrics).map((v, i) => (
                      <td key={i} className="px-4 py-3 text-right">
                        <span
                          className={`font-mono font-medium ${
                            v >= 0.7
                              ? 'text-green-400'
                              : v >= 0.4
                                ? 'text-yellow-400'
                                : 'text-red-400'
                          }`}
                        >
                          {(v * 100).toFixed(0)}%
                        </span>
                      </td>
                    ))}
                    <td className="px-4 py-3 text-right text-gray-400">
                      {r.trace_summary.total_tool_calls}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setViewingTrace(r)}
                        className="text-xs text-blue-400 hover:text-blue-300"
                      >
                        Trace →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button
            onClick={() => {
              setStep('upload')
              setParseResponse(null)
              setResults([])
            }}
            className="text-sm text-gray-400 hover:text-gray-200"
          >
            ← Evaluate another file
          </button>
        </div>
      )}

      {viewingTrace && (
        <TraceViewer result={viewingTrace} onClose={() => setViewingTrace(null)} />
      )}
    </div>
  )
}
