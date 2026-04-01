const STEPS = [
  { key: 'repo_ingestor', label: 'Ingest', desc: 'Clone & scan repository' },
  { key: 'code_chunker', label: 'Chunk', desc: 'Parse code into chunks' },
  { key: 'architecture_mapper', label: 'Map', desc: 'Build dependency graph' },
  { key: 'tech_debt_analyzer', label: 'Score', desc: 'Analyze code quality' },
  { key: 'qa_ready', label: 'Index', desc: 'Prepare vector search' },
]

const ORDER = ['idle', 'ingesting', 'chunking', 'mapping', 'analyzing_debt', 'qa_ready', 'completed', 'failed']
const IDX: Record<string, number> = {
  repo_ingestor: 1, code_chunker: 2, architecture_mapper: 3, tech_debt_analyzer: 4, qa_ready: 5,
}

function getState(key: string, st: string | null, agent: string | null) {
  if (st === 'failed' && agent === key) return 'failed'
  if (agent === key && st !== 'completed') return 'running'
  if (ORDER.indexOf(st || '') > IDX[key]) return 'done'
  return 'waiting'
}

interface Props {
  repoName: string
  githubUrl: string
  currentStatus: string | null
  currentAgent: string | null
  error: string | null
  onReset: () => void
}

export function ProgressView({ repoName, githubUrl, currentStatus, currentAgent, error, onReset }: Props) {
  const done = currentStatus === 'completed' || currentStatus === 'qa_ready'

  return (
    <section className="py-20 fade-in">
      <h2 className="text-xl font-semibold mb-1">{repoName}</h2>
      <a
        href={githubUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-stone-400 hover:text-stone-600 font-mono transition-colors"
      >
        {githubUrl}
      </a>

      <div className="mt-8 border border-stone-200 rounded-lg bg-white divide-y divide-stone-100">
        {STEPS.map(step => {
          const s = getState(step.key, currentStatus, currentAgent)
          return (
            <div key={step.key} className="flex items-center gap-3 px-4 py-3">
              <div className="w-5 flex justify-center shrink-0">
                {s === 'done' && (
                  <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
                {s === 'running' && (
                  <div className="w-2 h-2 rounded-full bg-teal-500 animate-pulse" />
                )}
                {s === 'failed' && (
                  <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                )}
                {s === 'waiting' && <div className="w-1.5 h-1.5 rounded-full bg-stone-300" />}
              </div>
              <span className={`text-sm ${
                s === 'waiting' ? 'text-stone-400'
                : s === 'running' ? 'text-stone-900 font-medium'
                : 'text-stone-700'
              }`}>
                {step.label}
              </span>
              <span className="text-xs text-stone-400 ml-auto">{step.desc}</span>
            </div>
          )
        })}
      </div>

      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-100 rounded-lg">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      <div className="mt-6 space-y-2">
        {done && <p className="text-sm text-green-600 font-medium">Analysis complete</p>}
        <button onClick={onReset} className="text-sm text-stone-400 hover:text-stone-600 transition-colors">
          Analyze another repo
        </button>
      </div>
    </section>
  )
}
