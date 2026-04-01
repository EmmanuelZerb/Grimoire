import { useEffect, useState } from 'react'
import { getReport } from '../lib/api'

interface Props { jobId: string }

function scoreMeta(score: number) {
  if (score >= 75) return { color: '#DB2777', bg: '#FDF2F8', label: 'Critical' }
  if (score >= 50) return { color: '#DC2626', bg: '#FEF2F2', label: 'High' }
  if (score >= 25) return { color: '#D97706', bg: '#FFFBEB', label: 'Medium' }
  return { color: '#16A34A', bg: '#F0FDF4', label: 'Low' }
}

function barColor(score: number) {
  if (score >= 75) return '#DB2777'
  if (score >= 50) return '#DC2626'
  if (score >= 25) return '#D97706'
  return '#16A34A'
}

export function TechDebtReport({ jobId }: Props) {
  const [report, setReport] = useState<any>(null)

  useEffect(() => {
    getReport(jobId).then(d => setReport(d.tech_debt)).catch(() => {})
  }, [jobId])

  if (!report) return <p className="text-sm text-stone-400 py-8">Loading…</p>

  const sc = scoreMeta(report.overall_score)

  return (
    <section>
      <h2 className="text-lg font-semibold mb-1">Tech debt</h2>
      <p className="text-sm text-stone-400 mb-6">Code quality analysis</p>

      {/* Score */}
      <div className="flex items-center gap-6 mb-8 p-5 bg-white border border-stone-200 rounded-lg">
        <div className="shrink-0">
          <div className="text-4xl font-bold tabular-nums" style={{ color: sc.color }}>
            {Math.round(report.overall_score)}
          </div>
          <span
            className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded mt-1 inline-block"
            style={{ color: sc.color, background: sc.bg }}
          >
            {sc.label}
          </span>
        </div>
        <p className="text-sm text-stone-500 leading-relaxed">
          {report.overall_score < 25
            ? 'Looking good. A few rough edges, nothing serious.'
            : report.overall_score < 50
            ? 'Some debt accumulating. Worth addressing soon.'
            : report.overall_score < 75
            ? 'Significant debt. Plan a cleanup sprint.'
            : 'Critical levels. Refactor before shipping.'}
        </p>
      </div>

      {/* Categories */}
      {report.categories?.length > 0 && (
        <div className="space-y-4 mb-8">
          {report.categories.map((cat: any) => (
            <div key={cat.name}>
              <div className="flex justify-between mb-1.5">
                <span className="text-sm">{cat.name}</span>
                <span className="text-xs text-stone-400 tabular-nums">{Math.round(cat.score)}</span>
              </div>
              <div className="h-1.5 bg-stone-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${cat.score}%`, background: barColor(cat.score) }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Two columns */}
      <div className="grid grid-cols-2 gap-4">
        {report.todos_fixmes?.length > 0 && (
          <div className="border border-stone-200 rounded-lg bg-white p-4">
            <div className="flex justify-between items-center mb-3">
              <h3 className="text-xs font-medium text-stone-400 uppercase tracking-wider">TODOs & FIXMEs</h3>
              <span className="text-xs text-stone-400">{report.todos_fixmes.length}</span>
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {report.todos_fixmes.slice(0, 10).map((t: any, i: number) => (
                <div key={i} className="flex gap-2">
                  <span className={`text-[10px] font-mono font-medium shrink-0 mt-0.5 ${
                    t.type === 'FIXME' ? 'text-red-500' : t.type === 'HACK' ? 'text-amber-600' : 'text-stone-400'
                  }`}>
                    {t.type}
                  </span>
                  <span className="text-[13px] text-stone-600 leading-snug line-clamp-2">{t.text}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {report.outdated_dependencies?.length > 0 && (
          <div className="border border-stone-200 rounded-lg bg-white p-4">
            <div className="flex justify-between items-center mb-3">
              <h3 className="text-xs font-medium text-stone-400 uppercase tracking-wider">Outdated deps</h3>
              <span className="text-xs text-stone-400">{report.outdated_dependencies.length}</span>
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {report.outdated_dependencies.slice(0, 10).map((d: any, i: number) => (
                <div key={i} className="flex gap-2">
                  <span className="text-[10px] font-mono text-teal-600 shrink-0 mt-0.5">{d.version}</span>
                  <div>
                    <span className="text-xs font-mono text-stone-700">{d.package}</span>
                    <span className="text-xs text-stone-400 ml-1">({d.file?.split('/').pop()})</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
