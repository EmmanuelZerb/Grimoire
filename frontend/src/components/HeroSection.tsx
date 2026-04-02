import { useState } from 'react'

interface Props {
  onAnalyze: (url: string) => void
  isLoading: boolean
  error: string | null
}

export function HeroSection({ onAnalyze, isLoading, error }: Props) {
  const [url, setUrl] = useState('')

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (url.trim()) onAnalyze(url.trim())
  }

  return (
    <section className="min-h-[60vh] flex flex-col justify-center items-center text-center fade-in">
      <div className="w-full max-w-2xl">
          <h1 className="text-[40px] sm:text-[52px] font-semibold tracking-tight text-[#171717] mb-4 leading-tight">
          Comprenez n'importe quel code
        </h1>

        <p className="text-[16px] text-[#737373] mb-10 max-w-lg mx-auto leading-relaxed">
          Générez instantanément des diagrammes d'architecture, des rapports de dette technique et interrogez n'importe quel dépôt GitHub en langage naturel.
        </p>

        <form onSubmit={submit} className="w-full relative z-10 mb-8 max-w-lg mx-auto">
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="url"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://github.com/proprietaire/depot"
              disabled={isLoading}
              className="flex-1 px-3.5 py-2.5 text-[14px] bg-white border border-[#eaeaea] rounded-md focus:outline-none focus:border-[#a3a3a3] focus:ring-1 focus:ring-[#a3a3a3] transition-all disabled:opacity-60 shadow-sm placeholder:text-[#a3a3a3]"
            />
            <button
              type="submit"
              disabled={isLoading || !url.trim()}
              className="px-5 py-2.5 text-[14px] font-medium text-white bg-[#171717] rounded-md hover:bg-[#262626] transition-colors disabled:opacity-50 shadow-sm"
            >
              {isLoading ? 'Analyse...' : 'Analyser le dépôt'}
            </button>
          </div>
          {error && (
             <div className="mt-3 text-[13px] text-red-600 font-medium text-left">
               {error}
             </div>
          )}
        </form>

        <div className="flex flex-col items-center gap-3 mt-12">
          <span className="text-[11px] font-medium text-[#a3a3a3] uppercase tracking-widest">Exemples de dépôts</span>
          <div className="flex flex-wrap justify-center gap-2">
            {['vercel/next.js', 'facebook/react', 'denoland/deno'].map(r => (
              <button
                key={r}
                onClick={() => setUrl(`https://github.com/${r}`)}
                className="text-[12px] text-[#525252] bg-white border border-[#eaeaea] px-2.5 py-1.5 rounded-md hover:bg-[#f5f5f5] hover:border-[#d4d4d4] transition-all shadow-xs font-mono"
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
