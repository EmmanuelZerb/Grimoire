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
    <section className="min-h-[calc(100vh-48px)] flex items-center justify-center">
      <div className="w-full max-w-[640px] text-center fade-in">
        <p className="text-[11px] uppercase tracking-[0.25em] text-stone-400 font-medium mb-6">
          Code Intelligence
        </p>

        <h1 className="font-serif italic text-[68px] sm:text-[76px] leading-[0.95] tracking-tight text-stone-900 mb-8">
          Understand<br />any codebase
        </h1>

        <p className="text-stone-400 text-[15px] leading-relaxed mb-12 max-w-[400px] mx-auto">
          Paste a GitHub URL to get architecture maps, tech debt analysis, and intelligent code search.
        </p>

        <form onSubmit={submit} className="max-w-[480px] mx-auto">
          <div className="flex rounded-lg border border-stone-200 bg-white shadow-sm focus-within:border-teal-500 focus-within:ring-2 focus-within:ring-teal-500/10 transition-all">
            <input
              type="url"
              value={url}
              onChange={e => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              disabled={isLoading}
              className="flex-1 px-4 py-3 text-sm bg-transparent focus:outline-none disabled:opacity-50 placeholder:text-stone-300"
            />
            <button
              type="submit"
              disabled={isLoading || !url.trim()}
              className="px-6 py-3 bg-teal-600 text-white text-sm font-medium hover:bg-teal-700 transition-colors disabled:opacity-40"
            >
              {isLoading ? '…' : 'Analyze'}
            </button>
          </div>
        </form>

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

        <div className="mt-8 flex justify-center gap-6">
          {['vercel/next.js', 'facebook/react', 'denoland/deno'].map(r => (
            <button
              key={r}
              onClick={() => setUrl(`https://github.com/${r}`)}
              className="text-xs text-stone-400 hover:text-stone-600 font-mono transition-colors"
            >
              {r}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
