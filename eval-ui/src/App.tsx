import { useState } from 'react'
import Layout from './components/Layout'
import Dashboard from './components/Dashboard'
import EvaluatePage from './components/EvaluatePage'
import CouchbasePage from './components/CouchbasePage'
import type { EvalResult } from './types'

export type Page = 'dashboard' | 'evaluate' | 'couchbase'

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [lastResults, setLastResults] = useState<EvalResult[]>([])
  const [lastRunId, setLastRunId] = useState<string>('')

  return (
    <Layout page={page} setPage={setPage}>
      {page === 'dashboard' && (
        <Dashboard setPage={setPage} lastResults={lastResults} />
      )}
      {page === 'evaluate' && (
        <EvaluatePage
          onResults={(runId, results) => {
            setLastRunId(runId)
            setLastResults(results)
          }}
        />
      )}
      {page === 'couchbase' && (
        <CouchbasePage runId={lastRunId} results={lastResults} />
      )}
    </Layout>
  )
}
