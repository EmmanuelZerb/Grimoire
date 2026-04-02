import { useEffect, useState } from 'react'

const STEPS = [
  { key: 'repo_ingestor', label: 'Acquisition', desc: 'Clonage et scan du dépôt' },
  { key: 'code_chunker', label: 'Traitement', desc: 'Analyse des arbres syntaxiques' },
  { key: 'architecture_mapper', label: 'Cartographie', desc: 'Génération du graphe de dépendances' },
  { key: 'tech_debt_analyzer', label: 'Analyse', desc: 'Évaluation de la qualité du code' },
  { key: 'qa_ready', label: 'Indexation', desc: 'Préparation de la base vectorielle' },
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

  // Small effect to trigger re-renders smoothly if needed
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])

  return (
    <section className={`py-12 max-w-[500px] mx-auto transition-opacity duration-500 ${mounted ? 'opacity-100' : 'opacity-0'}`}>
      <div className="bg-white border border-[#eaeaea] rounded-xl p-7 shadow-sm">
        <div className="mb-8 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-[16px] font-semibold tracking-tight text-[#171717] truncate mb-1">
              {repoName}
            </h2>
            <p className="text-[13px] text-[#737373] font-mono truncate">{githubUrl}</p>
          </div>
          <div className="shrink-0 mt-0.5">
            {done ? (
              <span className="inline-flex text-[12px] font-medium px-2.5 py-1 bg-[#f5f5f5] text-[#171717] rounded-md border border-[#eaeaea] animate-pop-in">
                Terminé
              </span>
            ) : (
              <span className="inline-flex text-[12px] font-medium px-2.5 py-1 bg-blue-50 text-blue-600 rounded-md border border-blue-100 items-center gap-1.5 shadow-sm">
                <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></span>
                En cours
              </span>
            )}
          </div>
        </div>

        <div className="relative space-y-0 ml-2">
          {/* Vertical connecting line */}
          <div className="absolute top-4 bottom-5 left-[7px] w-[2px] bg-[#f5f5f5] -z-10" />

          {STEPS.map((step, i) => {
            const s = getState(step.key, currentStatus, currentAgent)
            const isRunning = s === 'running'
            const isDone = s === 'done'
            const isFailed = s === 'failed'
            const isWaiting = s === 'waiting'
            
            return (
              <div 
                key={step.key} 
                className={`relative flex items-start gap-4 pb-6 last:pb-0 transition-all duration-500 ${
                  isRunning ? 'opacity-100 translate-x-0' : 
                  isWaiting ? 'opacity-40 translate-x-0' : 'opacity-100 translate-x-0'
                }`}
              >
                {/* Timeline Node */}
                <div className="relative mt-0.5 shrink-0 z-10 bg-white py-1">
                  {isDone ? (
                    <div className="w-4 h-4 rounded-full bg-[#171717] flex items-center justify-center animate-pop-in shadow-sm">
                      <svg className="w-2.5 h-2.5 text-white animate-checkmark" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  ) : isRunning ? (
                    <div className="w-4 h-4 rounded-full border-2 border-[#eaeaea] border-t-[#171717] animate-spin shadow-sm bg-white" />
                  ) : isFailed ? (
                    <div className="w-4 h-4 rounded-full bg-red-100 flex items-center justify-center shadow-sm">
                      <svg className="w-2.5 h-2.5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </div>
                  ) : (
                    <div className="w-4 h-4 rounded-full border-2 border-[#f5f5f5] bg-white transition-colors duration-300" />
                  )}
                </div>
                
                {/* Content */}
                <div className={`flex flex-col mt-[1px] transition-colors duration-300 ${isDone ? 'text-[#171717]' : isRunning ? 'text-[#171717]' : 'text-[#737373]'}`}>
                  <span className="text-[14px] font-medium leading-none mb-1.5">
                    {step.label}
                  </span>
                  <span className={`text-[13px] leading-snug ${isRunning ? 'text-[#525252]' : 'text-[#a3a3a3]'}`}>
                    {step.desc}
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        {error && (
          <div className="mt-8 p-3.5 bg-red-50 border border-red-100 rounded-lg text-[13px] text-red-700 animate-pop-in">
            <span className="font-semibold block mb-1">Échec de l'exécution</span>
            <span className="font-mono text-[12px] opacity-90">{error}</span>
          </div>
        )}

        <div className="mt-8 pt-5 border-t border-[#eaeaea] flex justify-end">
          <button 
            onClick={onReset} 
            className="text-[13px] font-medium text-[#737373] hover:text-[#171717] transition-colors bg-[#fafafa] hover:bg-[#f5f5f5] px-4 py-2 rounded-md border border-[#eaeaea] shadow-xs"
          >
            Annuler
          </button>
        </div>
      </div>
    </section>
  )
}