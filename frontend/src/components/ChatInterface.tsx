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

  const hints = ["Explique l'architecture", "Où sont les API ?", "Y a-t-il des problèmes de sécurité ?", "Comment fonctionne l'authentification ?"]

  return (
    <section className="bg-white rounded-lg border border-[#eaeaea] shadow-sm overflow-hidden flex flex-col h-full min-h-[500px] fade-in">
      <div className="p-5 border-b border-[#eaeaea] flex justify-between items-center shrink-0">
        <div>
          <h2 className="text-[16px] font-semibold text-[#171717] tracking-tight mb-0.5">Assistant Codebase</h2>
          <p className="text-[13px] text-[#737373]">Posez des questions sur le code analysé</p>
        </div>
      </div>

      <div ref={bottom} className="flex-1 overflow-y-auto p-5 space-y-5 bg-white">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-5">
            <div className="w-10 h-10 bg-[#fafafa] border border-[#eaeaea] rounded-md flex items-center justify-center">
              <svg className="w-4 h-4 text-[#737373]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </div>
            <div className="max-w-xs">
              <p className="text-[13px] text-[#737373]">Je suis prêt à répondre à vos questions sur ce projet. Que souhaitez-vous savoir ?</p>
            </div>
            
            <div className="flex flex-wrap justify-center gap-2 max-w-sm mt-2">
              {hints.map(h => (
                <button
                  key={h}
                  onClick={() => setInput(h)}
                  className="text-[12px] font-medium text-[#525252] bg-white border border-[#eaeaea] hover:bg-[#fafafa] px-2.5 py-1.5 rounded-md transition-colors shadow-xs"
                >
                  {h}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-lg px-3.5 py-2.5 text-[13px] leading-relaxed shadow-xs border ${
              m.role === 'user'
                ? 'bg-[#171717] text-white border-[#171717]'
                : 'bg-white text-[#171717] border-[#eaeaea]'
            }`}>
              <p className="whitespace-pre-wrap font-sans">{m.text}</p>
              
              {m.sources && m.sources.length > 0 && (
                <div className={`mt-2.5 pt-2 border-t ${m.role === 'user' ? 'border-[#404040]' : 'border-[#eaeaea]'}`}>
                  <p className={`text-[9px] font-semibold uppercase tracking-wider mb-1.5 ${m.role === 'user' ? 'text-[#a3a3a3]' : 'text-[#737373]'}`}>
                    Sources
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {m.sources.map((s: any, j: number) => (
                      <span key={j} className={`text-[10px] font-mono px-1.5 py-0.5 rounded border flex gap-1 ${
                        m.role === 'user' 
                          ? 'bg-[#262626] border-[#404040] text-[#d4d4d4]' 
                          : 'bg-[#fafafa] border-[#eaeaea] text-[#737373]'
                      }`}>
                        {s.name && <span className="font-semibold">{s.name}</span>}
                        <span className="opacity-80">{s.file_path}:{s.start_line}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-[#eaeaea] rounded-lg px-3.5 py-2.5 shadow-xs">
              <div className="flex gap-1 items-center h-4">
                <div className="w-1.5 h-1.5 bg-[#a3a3a3] rounded-full animate-bounce" />
                <div className="w-1.5 h-1.5 bg-[#a3a3a3] rounded-full animate-bounce" style={{ animationDelay: '0.15s' }} />
                <div className="w-1.5 h-1.5 bg-[#a3a3a3] rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-[#eaeaea] bg-[#fafafa] shrink-0">
        <form 
          className="relative flex items-center" 
          onSubmit={(e) => { e.preventDefault(); send() }}
        >
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Posez votre question..."
            disabled={loading}
            className="w-full pl-3 pr-10 py-2 bg-white border border-[#eaeaea] rounded-md text-[13px] focus:outline-none focus:border-[#a3a3a3] focus:ring-1 focus:ring-[#a3a3a3] transition-all disabled:opacity-50 font-sans shadow-xs placeholder:text-[#a3a3a3]"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="absolute right-1.5 p-1 rounded-md bg-[#171717] text-white hover:bg-[#262626] disabled:opacity-50 disabled:bg-[#a3a3a3] transition-colors flex items-center justify-center shadow-xs"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </button>
        </form>
      </div>
    </section>
  )
}
