import { useAnalysis } from './hooks/useAnalysis'
import { HeroSection } from './components/HeroSection'
import { ProgressView } from './components/ProgressView'
import { ArchitectureReport } from './components/ArchitectureReport'
import { TechDebtReport } from './components/TechDebtReport'
import { ChatInterface } from './components/ChatInterface'

export default function App() {
  const { phase, jobId, githubUrl, status, error, repoName, startAnalysis, reset } = useAnalysis()

  return (
    <div className="min-h-screen font-sans text-[#171717] bg-[#fafafa] pb-24 selection:bg-[#eaeaea]">
      {/* Nav */}
      <nav className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-[#eaeaea]">
        <div className="max-w-[1040px] mx-auto px-6 h-14 flex items-center justify-between">
          <button onClick={phase !== 'idle' ? reset : undefined} className="flex items-center gap-2.5">
            <div className="w-5 h-5 bg-[#171717] rounded-sm flex items-center justify-center">
              <div className="w-2 h-2 bg-white rounded-sm" />
            </div>
            <span className="text-[14px] font-semibold tracking-tight text-[#171717]">
              Grimoire
            </span>
          </button>
          
          {phase !== 'idle' && (
            <div className="flex items-center gap-3">
              <span className="text-[13px] text-[#737373] truncate max-w-[250px]">{repoName}</span>
              <div className="flex items-center h-5 px-2 bg-white border border-[#eaeaea] rounded-md shadow-xs">
                <div className={`w-1.5 h-1.5 rounded-full ${
                  phase === 'analyzing' ? 'bg-blue-500 animate-pulse' :
                  phase === 'completed' ? 'bg-[#171717]' : 'bg-red-500'
                }`} />
              </div>
            </div>
          )}
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
              <h1 className="text-2xl font-semibold tracking-tight text-[#171717] mb-1">Rapport d'analyse</h1>
              <p className="text-[14px] text-[#737373]">Vue d'ensemble, architecture et métriques de qualité de code pour {repoName}.</p>
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
