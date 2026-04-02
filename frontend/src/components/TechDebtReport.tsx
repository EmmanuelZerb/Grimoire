import { useEffect, useState } from 'react'
import { getReport } from '../lib/api'

interface Props { jobId: string }

function getScoreTheme(score: number) {
  if (score >= 75) return { color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200', bar: 'bg-red-500', label: 'Critique' }
  if (score >= 50) return { color: 'text-orange-600', bg: 'bg-orange-50', border: 'border-orange-200', bar: 'bg-orange-500', label: 'Élevée' }
  if (score >= 25) return { color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200', bar: 'bg-blue-500', label: 'Modérée' }
  return { color: 'text-green-600', bg: 'bg-green-50', border: 'border-green-200', bar: 'bg-green-500', label: 'Faible' }
}

export function TechDebtReport({ jobId }: Props) {
  const [report, setReport] = useState<any>(null)

  useEffect(() => {
    getReport(jobId).then(d => setReport(d.tech_debt)).catch(() => {})
  }, [jobId])

  if (!report) return (
    <div className="bg-white rounded-lg border border-[#eaeaea] p-6 shadow-sm flex items-center justify-center min-h-[300px] text-[#a3a3a3] text-[13px]">
      Évaluation de la dette technique...
    </div>
  )

  const theme = getScoreTheme(report.overall_score)

  return (
    <section className="bg-white rounded-lg border border-[#eaeaea] p-6 shadow-sm fade-in h-full flex flex-col">
      <div className="mb-5">
        <h2 className="text-[16px] font-semibold text-[#171717] mb-0.5 tracking-tight">Dette Technique</h2>
        <p className="text-[13px] text-[#737373]">Qualité du code et maintenabilité</p>
      </div>

      {/* Score Box */}
      <div className={`flex items-center gap-4 p-4 rounded-md border ${theme.bg} ${theme.border} mb-6`}>
        <div className="flex flex-col items-center shrink-0">
          <div className={`text-[32px] font-semibold tabular-nums tracking-tight ${theme.color} leading-none`}>
            {Math.round(report.overall_score)}
          </div>
        </div>
        <div>
          <div className={`text-[11px] font-semibold uppercase tracking-wider mb-0.5 ${theme.color}`}>
            Dette {theme.label}
          </div>
          <p className="text-[13px] text-[#404040]">
            {report.overall_score < 25
              ? 'Base de code saine. L\'architecture est bien maintenue.'
              : report.overall_score < 50
              ? 'La dette s\'accumule. Prévoyez des refactorisations mineures.'
              : report.overall_score < 75
              ? 'Dette technique importante. Un sprint de nettoyage est recommandé.'
              : 'Niveau critique. Refonte majeure requise avant de nouvelles fonctionnalités.'}
          </p>
        </div>
      </div>

      {/* Categories */}
      {report.categories?.length > 0 && (
        <div className="mb-6">
          <div className="space-y-3">
            {report.categories.map((cat: any) => {
              const catTheme = getScoreTheme(cat.score)
              return (
                <div key={cat.name}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-[12px] font-medium text-[#404040]">{cat.name}</span>
                    <span className="text-[12px] font-semibold text-[#171717] tabular-nums">{Math.round(cat.score)}</span>
                  </div>
                  <div className="h-1 w-full bg-[#f5f5f5] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${catTheme.bar}`}
                      style={{ width: `${cat.score}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Lists */}
      <div className="space-y-4 mt-auto">
        {report.todos_fixmes?.length > 0 && (
          <div>
            <h3 className="text-[11px] font-semibold text-[#737373] uppercase tracking-wider mb-2">TODOs & FIXMEs ({report.todos_fixmes.length})</h3>
            <div className="space-y-2 max-h-[150px] overflow-y-auto">
              {report.todos_fixmes.slice(0, 10).map((t: any, i: number) => (
                <div key={i} className="flex items-start gap-2">
                  <span className={`text-[9px] font-mono font-semibold px-1 py-0.5 rounded-[3px] shrink-0 mt-[3px] ${
                    t.type === 'FIXME' ? 'bg-red-50 text-red-600 border border-red-100' : 
                    t.type === 'HACK' ? 'bg-orange-50 text-orange-600 border border-orange-100' : 
                    'bg-[#f5f5f5] text-[#525252] border border-[#eaeaea]'
                  }`}>
                    {t.type}
                  </span>
                  <p className="text-[13px] text-[#525252] leading-snug truncate" title={t.text}>{t.text}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {report.outdated_dependencies?.length > 0 && (
          <div>
            <h3 className="text-[11px] font-semibold text-[#737373] uppercase tracking-wider mb-2 border-t border-[#eaeaea] pt-4">Dépendances Obsolètes ({report.outdated_dependencies.length})</h3>
            <div className="space-y-1 max-h-[150px] overflow-y-auto">
              {report.outdated_dependencies.slice(0, 10).map((d: any, i: number) => (
                <div key={i} className="flex justify-between items-center text-[13px]">
                  <div className="flex items-baseline gap-2 overflow-hidden">
                    <span className="font-mono font-medium text-[#171717] truncate">{d.package}</span>
                    <span className="text-[11px] text-[#a3a3a3] font-mono truncate">{d.file?.split('/').pop()}</span>
                  </div>
                  <span className="font-mono text-[11px] text-[#525252] shrink-0 ml-2">
                    {d.version}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
