import { useEffect, useRef, useState } from 'react'
import { getDiagram, getReport } from '../lib/api'
import mermaid from 'mermaid'

interface Props { jobId: string }

export function ArchitectureReport({ jobId }: Props) {
  const [diagram, setDiagram] = useState<any>(null)
  const [report, setReport] = useState<any>(null)
  const [tab, setTab] = useState<'graph' | 'info'>('graph')
  const mRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getDiagram(jobId).then(setDiagram).catch(() => {})
    getReport(jobId).then(setReport).catch(() => {})
  }, [jobId])

  useEffect(() => {
    if (!diagram || tab !== 'graph' || !mRef.current) return
    const id = 'mm' + Date.now()
    mermaid.initialize({
      startOnLoad: false,
      theme: 'base',
      themeVariables: {
        primaryColor: '#fafafa',
        primaryTextColor: '#171717',
        primaryBorderColor: '#e5e5e5',
        lineColor: '#a3a3a3',
        secondaryColor: '#f5f5f5',
        tertiaryColor: '#ffffff',
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: '12px',
        edgeLabelBackground: '#ffffff',
      },
    })
    mermaid.render(id, diagram.diagram).then(({ svg }) => {
      if (mRef.current) mRef.current.innerHTML = svg
    }).catch(() => {
      if (mRef.current) mRef.current.innerHTML = `<pre class="font-mono text-[12px] p-4 text-[#737373] overflow-x-auto">${diagram.diagram}</pre>`
    })
  }, [diagram, tab])

  const m = report?.manifest

  return (
    <section className="bg-white rounded-lg border border-[#eaeaea] p-6 shadow-sm fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
        <div>
          <h2 className="text-[16px] font-semibold text-[#171717] mb-0.5 tracking-tight">Architecture</h2>
          <p className="text-[13px] text-[#737373]">Graphe de dépendances et modules</p>
        </div>
        {diagram && (
           <span className="text-[12px] font-medium text-[#404040] bg-[#fafafa] border border-[#eaeaea] px-2.5 py-1 rounded-md self-start sm:self-auto font-mono">
             Pattern : {diagram.detected_pattern}
           </span>
        )}
      </div>

      {/* Stats */}
      {m && (
        <div className="flex items-center gap-6 mb-6">
          {[
            { v: m.total_files, l: 'Fichiers' },
            { v: m.total_lines?.toLocaleString(), l: 'Lignes' },
            { v: m.languages?.length ?? 0, l: 'Langages' },
            { v: diagram?.module_count ?? 0, l: 'Modules' },
          ].map(({ v, l }) => (
            <div key={l} className="flex items-baseline gap-2">
              <div className="text-[15px] font-semibold text-[#171717] tabular-nums">{v}</div>
              <div className="text-[12px] text-[#737373]">{l}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-6 border-b border-[#eaeaea] mb-5">
        {(['graph', 'info'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2.5 text-[13px] font-medium transition-colors border-b-2 -mb-[1px] ${
              tab === t
                ? 'border-[#171717] text-[#171717]'
                : 'border-transparent text-[#737373] hover:text-[#171717]'
            }`}
          >
            {t === 'graph' ? 'Diagramme' : 'Détails bruts'}
          </button>
        ))}
      </div>

      <div className="min-h-[300px]">
        {/* Graph */}
        {tab === 'graph' && (
          <div>
            {diagram ? (
              <div className="bg-[#fafafa] border border-[#eaeaea] rounded-md p-4 overflow-auto" style={{ maxHeight: '500px' }}>
                <div ref={mRef} className="mermaid-wrap flex justify-center" />
              </div>
            ) : (
              <div className="flex items-center justify-center h-[300px] text-[#a3a3a3] text-[13px]">
                Génération du diagramme...
              </div>
            )}
          </div>
        )}

        {/* Details */}
        {tab === 'info' && diagram && (
          <div className="space-y-6 animate-in fade-in">
            {m?.languages?.length > 0 && (
              <div>
                <h3 className="text-[13px] font-semibold text-[#171717] mb-2.5">Langages</h3>
                <div className="flex flex-wrap gap-2">
                  {m.languages.map((l: any) => (
                    <div key={l.name} className="flex items-center gap-2 px-2.5 py-1.5 bg-white rounded-md border border-[#eaeaea] shadow-xs">
                      <span className="font-medium text-[#171717] text-[12px]">{l.name}</span>
                      <span className="text-[11px] font-mono text-[#737373]">
                        {l.total_lines?.toLocaleString()} LOC
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {diagram.core_modules?.length > 0 && (
                <div>
                  <h3 className="text-[13px] font-semibold text-[#171717] mb-2.5">Modules Core</h3>
                  <div className="flex flex-wrap gap-2">
                    {diagram.core_modules.map((mod: string) => (
                      <span key={mod} className="text-[11px] font-mono px-2 py-1 bg-[#f5f5f5] text-[#171717] border border-[#eaeaea] rounded-md">
                        {mod}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              {diagram.orphan_modules?.length > 0 && (
                <div>
                  <h3 className="text-[13px] font-semibold text-[#171717] mb-2.5">Modules orphelins</h3>
                  <div className="flex flex-wrap gap-2">
                    {diagram.orphan_modules.map((mod: string) => (
                      <span key={mod} className="text-[11px] font-mono px-2 py-1 bg-white text-[#737373] border border-[#eaeaea] rounded-md">
                        {mod}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {diagram.dependency_cycles?.length > 0 && (
              <div className="p-3 bg-white border border-red-200 rounded-md">
                <h3 className="text-[13px] font-semibold text-red-600 mb-2">
                  Cycles de dépendances ({diagram.dependency_cycles.length})
                </h3>
                <div className="space-y-1.5">
                  {diagram.dependency_cycles.slice(0, 5).map((c: string[], i: number) => (
                    <div key={i} className="text-[11px] font-mono text-red-600 bg-red-50 px-2 py-1 rounded border border-red-100 truncate">
                      {c.join(' ↔ ')}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
