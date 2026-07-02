export interface SessionSummary {
  session_id: string
  span_name: string
  message_count: number
  metadata: Record<string, unknown>
}

export interface ParseResponse {
  run_id: string
  session_count: number
  sessions: SessionSummary[]
}

export interface EvalResult {
  id: string
  type: string
  session_id: string
  span_name: string
  timestamp: string
  metrics: Record<string, number>
  trace_summary: {
    total_tool_calls: number
    unique_tools: string[]
    tool_sequence: string[]
    num_turns: number
  }
  metadata: Record<string, unknown>
  sample_preview: Array<{ role: string; content: string }>
}

export interface EvalRunResponse {
  run_id: string
  status: string
  result_count: number
  results: EvalResult[]
}

export interface AvailableMetric {
  id: string
  name: string
  description: string
  requires_reference: boolean
}

export interface CouchbaseConfig {
  connection_string: string
  username: string
  password: string
  bucket_name: string
  scope_name: string
  collection_name: string
}
