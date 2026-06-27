import type {
  AvailableMetric,
  CouchbaseConfig,
  EvalRunResponse,
  ParseResponse,
} from '../types'

const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail ?? 'Request failed')
  }
  return res.json() as Promise<T>
}

export async function parseTraces(file: File): Promise<ParseResponse> {
  const form = new FormData()
  form.append('file', file)
  return request<ParseResponse>('/parse', { method: 'POST', body: form })
}

export async function runEvaluation(
  run_id: string,
  metrics: string[],
  llm_model: string,
  openai_api_key?: string,
): Promise<EvalRunResponse> {
  return request<EvalRunResponse>('/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id, metrics, llm_model, openai_api_key }),
  })
}

export async function saveToCouchbase(
  run_id: string,
  config: CouchbaseConfig,
): Promise<{ written: number; total: number }> {
  return request('/save-to-couchbase', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id, couchbase: config }),
  })
}

export async function getAvailableMetrics(): Promise<AvailableMetric[]> {
  return request<AvailableMetric[]>('/available-metrics')
}

export async function getExampleQueries(): Promise<Record<string, string>> {
  return request<Record<string, string>>('/example-queries')
}
