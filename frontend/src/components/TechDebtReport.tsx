import { useEffect, useState } from 'react'
import { getReport } from '../lib/api'

interface Props { jobId: string }

function getSeverityLabel(score: number) {
  if (score >= 75) return 'Critique'
  if (score >= 50) return 'Élevée'
  if (score >= 25) return 'Modérée'
  return 'Faible'
}

function getBarOpacity(score: number) {
  if (score >= 75) return 1
  if (score >= 50) return 0.75
  if (score >= 25) return 0.5
  return 0.3
}

export function TechDebtReport({ jobId }: Props) {
  const [report, setReport] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    getReport(jobId).then(d => setReport(d.tech_debt)).catch(() => {})
  }, [jobId])

  if (!report) return (
    <div className="bg-[var(--bg-card)] rounded-lg border border-[var(--border)] p-6 shadow-sm flex items-center justify-center h-full min-h-[300px] text-[var(--text-faint)] text-[13px]">
      Évaluation de la dette technique...
    </div>
  )

  const overallScore = report.overall_score as number
  const categories = (report.categories as Array<{ name: string; score: number }>) ?? []
  const todosCount = ((report.todos_fixmes as unknown[]) ?? []).length
  const depsCount = ((report.outdated_dependencies as unknown[]) ?? []).length

  return (
    <section className="bg-[var(--bg-card)] rounded-lg border border-[var(--border)] p-6 shadow-sm fade-in flex flex-col">
      {/* Header */}
      <div className="mb-5">
        <h2 className="text-[16px] font-semibold text-[var(--text)] mb-0.5 tracking-tight">Dette Technique</h2>
        <p className="text-[13px] text-[var(--text-muted)]">Qualité du code et maintenabilité</p>
      </div>

      {/* Score */}
      <div className="flex items-center gap-4 p-4 rounded-lg border border-[var(--border)] bg-[var(--bg-subtle)] mb-5">
        <div className={`text-[36px] font-semibold tabular-nums tracking-tight leading-none ${
          overallScore < 25 ? 'text-[var(--color-success)]' :
          overallScore < 50 ? 'text-[var(--color-primary)]' :
          overallScore < 75 ? 'text-[var(--color-warning)]' :
          'text-[var(--color-danger)]'
        }`}>
          {Math.round(overallScore)}
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
            {getSeverityLabel(overallScore)}
          </div>
          <p className="text-[12px] text-[var(--text-secondary)] mt-0.5 leading-relaxed">
            {overallScore < 25
              ? 'Base de code saine.'
              : overallScore < 50
              ? 'Dette modérée, refactorisations ponctuelles recommandées.'
              : overallScore < 75
              ? 'Dette importante, un sprint de nettoyage est recommandé.'
              : 'Niveau critique. Refonte majeure requise.'}
          </p>
        </div>
      </div>

      {/* Categories */}
      {categories.length > 0 && (
        <div className="mb-5">
          <div className="space-y-2.5">
            {categories.map((cat) => (
              <div key={cat.name} className="flex items-center gap-3">
                <span className="text-[12px] text-[var(--text-secondary)] w-28 shrink-0 truncate" title={cat.name}>{cat.name}</span>
                <div className="flex-1 h-1.5 bg-[var(--bg-subtle)] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${
                      cat.score >= 75 ? 'bg-[var(--color-danger)]' :
                      cat.score >= 50 ? 'bg-[var(--color-warning)]' :
                      cat.score >= 25 ? 'bg-[var(--color-primary)]' :
                      'bg-[var(--color-success)]'
                    }`}
                    style={{ width: `${cat.score}%`, opacity: getBarOpacity(cat.score) }}
                  />
                </div>
                <span className="text-[12px] font-semibold tabular-nums w-8 text-right shrink-0 text-[var(--text)]">
                  {Math.round(cat.score)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick counts */}
      <div className="mt-auto flex items-center gap-4 pt-4 border-t border-[var(--border)]">
        {todosCount > 0 && (
          <Tooltip text={`${todosCount} marqueurs TODO, FIXME et HACK trouvés dans le code source.`}>
            <div className="flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="text-[var(--text-faint)]">
                <path d="M8 1v2M8 5v2M8 9v2M8 13v2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              <span className="font-medium">{todosCount}</span>
              <span className="text-[var(--text-faint)]">TODOs</span>
            </div>
          </Tooltip>
        )}
        {depsCount > 0 && (
          <Tooltip text={`${depsCount} dépendances avec des versions obsolètes détectées dans les requirements.`}>
            <div className="flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" className="text-[var(--text-faint)]">
                <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              <span className="font-medium">{depsCount}</span>
              <span className="text-[var(--text-faint)]">obsolètes</span>
            </div>
          </Tooltip>
        )}
      </div>
    </section>
  )
}

/* ── Tiny Tooltip ──────────────────────────────── */

function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  return (
    <span className="group/tip relative inline-flex">
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-[12px] leading-snug text-[var(--accent-text)] bg-[var(--text)] rounded-lg shadow-lg opacity-0 group-hover/tip:opacity-100 transition-opacity duration-200 whitespace-normal w-max max-w-[240px] z-50 text-center">
        {text}
        <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-[var(--text)]" />
      </span>
    </span>
  )
}
