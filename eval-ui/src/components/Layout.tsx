import type { Dispatch, PropsWithChildren, SetStateAction } from 'react'
import type { Page } from '../App'

const NAV: { id: Page; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: '\u{1F4CA}' },
  { id: 'evaluate', label: 'Evaluate', icon: '\u{1F52C}' },
  { id: 'couchbase', label: 'Couchbase', icon: '\u{1F5C4}️' },
]

interface Props extends PropsWithChildren {
  page: Page
  setPage: Dispatch<SetStateAction<Page>>
}

export default function Layout({ page, setPage, children }: Props) {
  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      <aside className="w-56 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <h1 className="text-lg font-bold text-blue-400">Ragas</h1>
          <p className="text-xs text-gray-500">Agent Evaluator</p>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {NAV.map(({ id, label, icon }) => (
            <button
              key={id}
              onClick={() => setPage(id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                page === id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
              }`}
            >
              <span>{icon}</span>
              {label}
            </button>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-800 text-xs text-gray-600">
          ragas × agentc
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  )
}
