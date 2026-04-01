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
        primaryColor: '#f5f5f4',
        primaryTextColor: '#1c1917',
        primaryBorderColor: '#d6d3d1',
        lineColor: '#d6d3d1',
        secondaryColor: '#fafaf9',
        tertiaryColor: '#f5f5f4',
        fontFamily: '"JetBrains Mono", monospace',
        fontSize: '12px',
      },
    })
    mermaid.render(id, diagram.diagram).then(({ svg }) => {
      if (mRef.current) mRef.current.innerHTML = svg
    }).catch(() => {
      if (mRef.current) mRef.current.innerHTML = `<pre class="font-mono text-xs p-4 text-stone-500">${diagram.diagram}</pre>`
    })
  }, [diagram, tab])

  const m = report?.manifest

  return (
    <section>
      <h2 className="text-lg font-semibold mb-1">Architecture</h2>
      <p className="text-sm text-stone-400 mb-6">Dependency graph and module overview</p>

      {/* Stats */}
      {m && (
        <div className="grid grid-cols-4 gap-6 mb-8">
          {[
            { v: m.total_files, l: 'Files' },
            { v: m.total_lines?.toLocaleString(), l: 'Lines' },
            { v: m.languages?.length ?? 0, l: 'Languages' },
            { v: diagram?.module_count ?? 0, l: 'Modules' },
          ].map(({ v, l }) => (
            <div key={l}>
              <div className="text-2xl font-bold tabular-nums">{v}</div>
              <div className="text-xs text-stone-400 mt-0.5">{l}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-6 border-b border-stone-200 mb-6">
        {(['graph', 'info'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2.5 text-sm font-medium transition-colors -mb-px ${
              tab === t
                ? 'text-stone-900 border-b-2 border-stone-900'
                : 'text-stone-400 hover:text-stone-600'
            }`}
          >
            {t === 'graph' ? 'Diagram' : 'Details'}
          </button>
        ))}
      </div>

      {/* Graph */}
      {tab === 'graph' && (
        <div>
          {diagram ? (
            <>
              <div className="mb-4">
                <span className="text-xs font-mono px-2 py-1 bg-teal-50 text-teal-700 rounded">
                  {diagram.detected_pattern}
                </span>
              </div>
              <div className="border border-stone-200 rounded-lg p-4 bg-white overflow-auto">
                <div ref={mRef} className="mermaid-wrap" />
              </div>
            </>
          ) : (
            <p className="text-sm text-stone-400 py-8">Loading diagram…</p>
          )}
        </div>
      )}

      {/* Details */}
      {tab === 'info' && diagram && (
        <div className="space-y-6">
          {m?.languages?.length > 0 && (
            <div>
              <h3 className="text-xs font-medium text-stone-400 uppercase tracking-wider mb-3">Languages</h3>
              <div className="space-y-2">
                {m.languages.map((l: any) => (
                  <div key={l.name} className="flex items-center justify-between">
                    <span className="text-sm">{l.name}</span>
                    <span className="text-xs text-stone-400 font-mono">
                      {l.total_lines?.toLocaleString()} lines · {l.file_count} files
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-6">
            {diagram.core_modules?.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-stone-400 uppercase tracking-wider mb-3">Core modules</h3>
                <div className="flex flex-wrap gap-1.5">
                  {diagram.core_modules.map((mod: string) => (
                    <span key={mod} className="text-xs font-mono px-2 py-0.5 bg-stone-100 text-stone-600 rounded">
                      {mod}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {diagram.orphan_modules?.length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-stone-400 uppercase tracking-wider mb-3">Orphan modules</h3>
                <div className="flex flex-wrap gap-1.5">
                  {diagram.orphan_modules.map((mod: string) => (
                    <span key={mod} className="text-xs font-mono px-2 py-0.5 bg-stone-50 text-stone-400 rounded">
                      {mod}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {diagram.dependency_cycles?.length > 0 && (
            <div>
              <h3 className="text-xs font-medium text-red-500 uppercase tracking-wider mb-3">
                Dependency cycles ({diagram.dependency_cycles.length})
              </h3>
              {diagram.dependency_cycles.slice(0, 5).map((c: string[], i: number) => (
                <p key={i} className="text-xs font-mono text-red-500/80 py-0.5">
                  {c.join(' → ')}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
