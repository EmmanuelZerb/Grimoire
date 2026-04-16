import { useAnalysis } from './hooks/useAnalysis'
import { HeroSection } from './components/HeroSection'
import { ProgressView } from './components/ProgressView'
import { ArchitectureReport } from './components/ArchitectureReport'
import { TechDebtReport } from './components/TechDebtReport'
import { ChatInterface } from './components/ChatInterface'

export default function App() {
  const { phase, jobId, githubUrl, status, error, repoName, startAnalysis, reset } = useAnalysis()

  return (
    <div className="min-h-screen font-sans text-[var(--text)] bg-[var(--bg)] pb-24 selection:bg-[var(--border)]">
      {/* Nav */}
      <nav className="sticky top-0 z-40 bg-[var(--bg-card)]/80 backdrop-blur-md border-b border-[var(--border)]">
        <div className="max-w-[1040px] mx-auto px-6 h-14 flex items-center justify-between">
          <button onClick={phase !== 'idle' ? reset : undefined} className="flex items-center gap-2.5">
            <img src="/grimoire.svg" alt="" width="20" height="24" className="text-[var(--text)]" />
            <span className="text-[14px] font-semibold tracking-tight text-[var(--text)]">
              Grimoire
            </span>
          </button>

          <div className="flex items-center gap-3">
            {phase !== 'idle' && (
              <div className="flex items-center gap-3">
                <span className="text-[13px] text-[var(--text-muted)] truncate max-w-[250px]">{repoName}</span>
                <div className="flex items-center h-5 px-2 bg-[var(--bg-card)] border border-[var(--border)] rounded-md shadow-xs">
                  <div className={`w-1.5 h-1.5 rounded-full ${
                    phase === 'analyzing' ? 'bg-[var(--color-primary)] animate-pulse' :
                    phase === 'completed' ? 'bg-[var(--color-success)]' : 'bg-[var(--color-danger)]'
                  }`} />
                </div>
              </div>
            )}
          </div>
        </div>
      </nav>

      <main className="max-w-[1040px] mx-auto px-6 mt-12">
        {phase === 'idle' && (
          <HeroSection onAnalyze={startAnalysis} isLoading={false} error={error} />
        )}

        {(phase === 'analyzing' || phase === 'failed') && (
          <ProgressView
            repoName={repoName}
            githubUrl={githubUrl}
            currentStatus={status?.status ?? null}
            currentAgent={status?.current_step ?? null}
            error={phase === 'failed' ? error : null}
            onReset={reset}
          />
        )}

        {phase === 'completed' && jobId && (
          <div className="fade-in space-y-6">
            <ArchitectureReport jobId={jobId} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-stretch">
              <TechDebtReport jobId={jobId} />
              <ChatInterface jobId={jobId} />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
