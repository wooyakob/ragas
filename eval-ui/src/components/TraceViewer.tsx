import type { EvalResult } from '../types'

interface Props {
  result: EvalResult
  onClose: () => void
}

const ROLE_STYLES: Record<string, string> = {
  human: 'bg-blue-900 border-blue-700 text-blue-100',
  ai: 'bg-gray-800 border-gray-600 text-gray-100',
  tool: 'bg-green-900 border-green-700 text-green-100',
}

export default function TraceViewer({ result, onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div>
            <p className="font-semibold text-gray-100">Trace Viewer</p>
            <p className="text-xs text-gray-400 mt-0.5">
              {result.span_name} · {result.session_id.slice(0, 8)}…
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-100 text-xl leading-none"
          >
            ×
          </button>
        </div>

        <div className="flex gap-4 px-4 py-3 border-b border-gray-800 overflow-x-auto">
          {Object.entries(result.metrics).map(([k, v]) => (
            <div key={k} className="flex-shrink-0 text-center">
              <p className="text-xs text-gray-500">{k.replace(/_/g, ' ')}</p>
              <p className="text-sm font-bold text-blue-400">{(v * 100).toFixed(0)}%</p>
            </div>
          ))}
          <div className="flex-shrink-0 text-center">
            <p className="text-xs text-gray-500">tool calls</p>
            <p className="text-sm font-bold text-purple-400">
              {result.trace_summary.total_tool_calls}
            </p>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {result.sample_preview.map((msg, i) => (
            <div
              key={i}
              className={`border rounded-lg p-3 text-sm ${
                ROLE_STYLES[msg.role] ?? 'bg-gray-800 border-gray-600 text-gray-200'
              }`}
            >
              <span className="text-xs font-semibold uppercase tracking-wider opacity-60 block mb-1">
                {msg.role}
              </span>
              <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
