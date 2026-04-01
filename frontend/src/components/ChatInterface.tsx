import { useState, useRef, useEffect } from 'react'
import { sendChat } from '../lib/api'

interface Props { jobId: string; repoName?: string }

export function ChatInterface({ jobId }: Props) {
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'ai'; text: string; sources?: any[] }>>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottom.current?.scrollTo({ top: bottom.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  const send = async () => {
    const q = input.trim()
    if (!q || loading) return
    setInput('')
    setMessages(p => [...p, { role: 'user', text: q }])
    setLoading(true)
    try {
      const res = await sendChat(jobId, q)
      setMessages(p => [...p, { role: 'ai', text: res.answer, sources: res.sources }])
    } catch (e: any) {
      setMessages(p => [...p, { role: 'ai', text: e.message }])
    } finally {
      setLoading(false)
    }
  }

  const hints = ['architecture overview', 'entry points', 'biggest debt', 'complex files']

  return (
    <section>
      <h2 className="text-lg font-semibold mb-1">Ask</h2>
      <p className="text-sm text-stone-400 mb-6">Search through the codebase</p>

      <div className="border border-stone-200 rounded-lg bg-white overflow-hidden">
        {/* Messages */}
        <div ref={bottom} className="h-[340px] overflow-y-auto p-4 space-y-3">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3">
              <p className="text-sm text-stone-400">Ask anything about this codebase</p>
              <div className="flex gap-1.5">
                {hints.map(h => (
                  <button
                    key={h}
                    onClick={() => setInput(h)}
                    className="text-xs text-stone-400 hover:text-stone-600 px-2.5 py-1 bg-stone-50 rounded transition-colors"
                  >
                    {h}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'flex justify-end' : ''}>
              <div className={`max-w-[85%] px-3.5 py-2.5 rounded-lg text-sm leading-relaxed ${
                m.role === 'user'
                  ? 'bg-teal-600 text-white'
                  : 'bg-stone-50 text-stone-700'
              }`}>
                <p className="whitespace-pre-wrap">{m.text}</p>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-stone-50 px-3.5 py-2.5 rounded-lg">
                <div className="flex gap-1">
                  <div className="w-1 h-1 rounded-full bg-stone-400 animate-bounce" />
                  <div className="w-1 h-1 rounded-full bg-stone-400 animate-bounce" style={{ animationDelay: '100ms' }} />
                  <div className="w-1 h-1 rounded-full bg-stone-400 animate-bounce" style={{ animationDelay: '200ms' }} />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Sources */}
        {(() => {
          const last = messages[messages.length - 1]
          if (!last?.sources || last.sources.length === 0) return null
          return (
            <div className="px-4 py-2 border-t border-stone-100">
              <div className="flex flex-wrap gap-1">
                {last.sources.map((s: any, j: number) => (
                  <span key={j} className="text-[10px] font-mono text-stone-400 bg-stone-50 px-1.5 py-0.5 rounded">
                    {s.name && <span className="text-stone-600">{s.name}</span>} {s.file_path}:{s.start_line}
                  </span>
                ))}
              </div>
            </div>
          )
        })()}

        {/* Input */}
        <div className="border-t border-stone-200 p-3">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
              placeholder="Ask about the code…"
              disabled={loading}
              className="flex-1 px-3 py-2 text-sm bg-stone-50 border border-stone-200 rounded-lg focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/20 disabled:opacity-50 placeholder:text-stone-300"
            />
            <button
              onClick={send}
              disabled={loading || !input.trim()}
              className="px-4 py-2 bg-stone-900 text-white text-sm font-medium rounded-lg hover:bg-stone-800 transition-colors disabled:opacity-40"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
