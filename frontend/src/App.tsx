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
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ transform: 'rotate(-25deg)' }}>
              {/* Book body */}
              <rect x="3" y="4" width="16" height="18" rx="2" fill="#171717"/>
              {/* Spine shadow */}
              <rect x="3" y="4" width="2.5" height="18" rx="1" fill="#000" opacity=".2"/>
              {/* Pages edge */}
              <rect x="4.5" y="5.5" width="13.5" height="15" rx="1" fill="#fff" opacity=".06"/>
              {/* Star/rune symbol */}
              <circle cx="11" cy="11" r="2.5" stroke="#fff" strokeWidth=".8" fill="none" opacity=".5"/>
              <circle cx="11" cy="11" r=".7" fill="#fff" opacity=".5"/>
              {/* Decorative lines below */}
              <line x1="7" y1="15.5" x2="15" y2="15.5" stroke="#fff" strokeWidth=".6" strokeLinecap="round" opacity=".2"/>
              <line x1="8" y1="17.5" x2="14" y2="17.5" stroke="#fff" strokeWidth=".6" strokeLinecap="round" opacity=".12"/>
            </svg>
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
                    phase === 'analyzing' ? 'bg-blue-500 animate-pulse' :
                    phase === 'completed' ? 'bg-[var(--accent)]' : 'bg-red-500'
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
            <div className="mb-8">
              <h1 className="text-2xl font-semibold tracking-tight text-[var(--text)] mb-1">Rapport d'analyse</h1>
              <p className="text-[14px] text-[var(--text-muted)]">Vue d'ensemble, architecture et métriques de qualité de code pour {repoName}.</p>
            </div>

            <ArchitectureReport jobId={jobId} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <TechDebtReport jobId={jobId} />
              <ChatInterface jobId={jobId} />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
