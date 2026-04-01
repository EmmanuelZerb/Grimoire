import { useAnalysis } from './hooks/useAnalysis'
import { HeroSection } from './components/HeroSection'
import { ProgressView } from './components/ProgressView'
import { ArchitectureReport } from './components/ArchitectureReport'
import { TechDebtReport } from './components/TechDebtReport'
import { ChatInterface } from './components/ChatInterface'

export default function App() {
  const { phase, jobId, githubUrl, status, error, repoName, startAnalysis, reset } = useAnalysis()

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <nav className="border-b border-stone-200 bg-white/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-[720px] mx-auto px-6 h-12 flex items-center justify-between">
          <button onClick={phase !== 'idle' ? reset : undefined} className="text-[15px] font-semibold tracking-tight hover:opacity-70 transition-opacity">
            grimoire
          </button>
          {phase !== 'idle' && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-stone-500">{repoName}</span>
              <span className={`w-1.5 h-1.5 rounded-full ${
                phase === 'analyzing' ? 'bg-teal-500 animate-pulse' :
                phase === 'completed' ? 'bg-green-500' : 'bg-red-500'
              }`} />
            </div>
          )}
        </div>
      </nav>

      <main className="max-w-[720px] mx-auto px-6">
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
          <div className="py-16 space-y-16">
            <ArchitectureReport jobId={jobId} />
            <TechDebtReport jobId={jobId} />
            <ChatInterface jobId={jobId} />
          </div>
        )}
      </main>
    </div>
  )
}
