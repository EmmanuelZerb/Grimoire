import { useState } from 'react'

interface Props {
  onAnalyze: (url: string) => void
  isLoading: boolean
  error: string | null
}

export function HeroSection({ onAnalyze, isLoading, error }: Props) {
  const [url, setUrl] = useState('')

  const [validationError, setValidationError] = useState<string | null>(null)

  const normalizeUrl = (raw: string): string | null => {
    const trimmed = raw.trim()
    if (!trimmed) return null

    let url = trimmed
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      if (url.startsWith('github.com/')) url = `https://${url}`
      else url = `https://github.com/${url}`
    }

    // Must match https://github.com/owner/repo
    const githubPattern = /^https?:\/\/github\.com\/[\w.-]+\/[\w.-]+(\/.*)?$/
    if (!githubPattern.test(url)) return null
    return url
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setValidationError(null)
    const normalized = normalizeUrl(url)
    if (!normalized) {
      setValidationError('URL invalide. Format attendu : github.com/proprietaire/depot')
      return
    }
    onAnalyze(normalized)
  }

  return (
    <section className="min-h-[60vh] flex flex-col justify-center items-center text-center fade-in">
      <div className="w-full max-w-2xl">
          <h1 className="text-[40px] sm:text-[52px] font-semibold tracking-tight text-[var(--text)] mb-4 leading-tight">
          Comprenez n'importe quel code
        </h1>

        <p className="text-[16px] text-[var(--text-muted)] mb-10 max-w-lg mx-auto leading-relaxed">
          Générez instantanément des diagrammes d'architecture, des rapports de dette technique et interrogez n'importe quel dépôt GitHub en langage naturel.
        </p>

        <form onSubmit={submit} className="w-full relative z-10 mb-8 max-w-lg mx-auto">
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://github.com/proprietaire/depot"
              disabled={isLoading}
              className="flex-1 px-3.5 py-2.5 text-[14px] bg-[var(--bg-card)] border border-[var(--border)] rounded-md focus:outline-none focus:border-[var(--text-faint)] focus:ring-1 focus:ring-[var(--text-faint)] transition-all disabled:opacity-60 shadow-sm placeholder:text-[var(--text-faint)]"
            />
            <button
              type="submit"
              disabled={isLoading || !url.trim()}
              className="px-5 py-2.5 text-[14px] font-medium text-[var(--accent-text)] bg-[var(--text)] rounded-md hover:bg-[var(--text-secondary)] transition-colors disabled:opacity-50 shadow-sm"
            >
              {isLoading ? 'Analyse...' : 'Analyser le dépôt'}
            </button>
          </div>
          {(error || validationError) && (
             <div className="mt-3 text-[13px] text-red-600 font-medium text-left">
               {validationError || error}
             </div>
          )}
        </form>

        <div className="flex flex-col items-center gap-3 mt-12">
          <span className="text-[11px] font-medium text-[var(--text-faint)] uppercase tracking-widest">Exemples de dépôts</span>
          <div className="flex flex-wrap justify-center gap-2">
            {['vercel/next.js', 'facebook/react', 'denoland/deno'].map(r => (
              <button
                key={r}
                onClick={() => setUrl(`https://github.com/${r}`)}
                className="text-[12px] text-[var(--text-faint)] bg-[var(--bg-card)] border border-[var(--border)] px-2.5 py-1.5 rounded-md hover:bg-[var(--bg-subtle)] hover:border-[var(--border-strong)] transition-all shadow-xs font-mono"
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
