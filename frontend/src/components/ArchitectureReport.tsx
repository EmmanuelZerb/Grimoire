import { useEffect, useState, useCallback } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { getDiagram, getReport, getReadme, streamGenerateReadme } from '../lib/api'
import { MermaidDiagram } from './MermaidDiagram'

interface Props { jobId: string }

interface DiagramData {
  detected_pattern: string
  diagram: string
  entry_points: string[]
  core_modules: string[]
  orphan_modules: string[]
  dependency_cycles: string[][]
  module_count: number
  dependency_graph: Record<string, string[]>
}

type Tab = 'graph' | 'readme' | 'info'

/* ── Tooltip ───────────────────────────────────── */

function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  return (
    <span className="group/tip relative inline-flex">
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-[12px] leading-snug text-white bg-[var(--text)] rounded-lg shadow-lg opacity-0 group-hover/tip:opacity-100 transition-opacity duration-200 whitespace-normal w-max max-w-[240px] z-50 text-center">
        {text}
        <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-[var(--text)]" />
      </span>
    </span>
  )
}

/* ── Insight Card ───────────────────────────────── */

function InsightCard({
  icon,
  label,
  tooltip,
  items,
}: {
  icon: React.ReactNode
  label: string
  tooltip: string
  items: string[]
}) {
  if (items.length === 0) return null
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-6 min-w-[320px] flex-1">
      <div className="flex items-center gap-3 mb-4">
        <span className="text-[var(--text-muted)]">{icon}</span>
        <Tooltip text={tooltip}>
          <span className="text-[13px] font-semibold uppercase tracking-wider text-[var(--text-muted)] cursor-help underline decoration-dotted decoration-[var(--border-strong)] underline-offset-4">{label}</span>
        </Tooltip>
        <span className="text-[12px] tabular-nums text-[var(--text-faint)] bg-[var(--bg-subtle)] px-2.5 py-1 rounded-full font-medium">
          {items.length}
        </span>
      </div>
      <div className="flex flex-wrap gap-2.5">
        {items.map((item) => (
          <span
            key={item}
            className="text-[13px] font-mono px-3 py-2 rounded-md bg-[var(--bg-subtle)] text-[var(--text-secondary)] border border-[var(--border)] whitespace-nowrap"
            title={item}
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ── Custom Markdown Renderer ───────────────────── */

function ReadmeRenderer({ content }: { content: string }) {
  return (
    <article className="readme-doc">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="readme-h1">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="readme-h2">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="readme-h3">{children}</h3>
          ),
          p: ({ children }) => (
            <p className="readme-p">{children}</p>
          ),
          a: ({ href, children }) => (
            <a href={href} className="readme-a" target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
          code: ({ className, children }) => {
            const isBlock = className?.includes('language-')
            if (isBlock) {
              return (
                <code className={className}>{children}</code>
              )
            }
            return <code className="readme-inline-code">{children}</code>
          },
          pre: ({ children }) => (
            <pre className="readme-code-block">{children}</pre>
          ),
          blockquote: ({ children }) => (
            <blockquote className="readme-blockquote">{children}</blockquote>
          ),
          ul: ({ children }) => (
            <ul className="readme-ul">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="readme-ol">{children}</ol>
          ),
          li: ({ children }) => (
            <li className="readme-li">{children}</li>
          ),
          table: ({ children }) => (
            <div className="readme-table-wrap">
              <table className="readme-table">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="readme-th">{children}</th>
          ),
          td: ({ children }) => (
            <td className="readme-td">{children}</td>
          ),
          hr: () => <hr className="readme-hr" />,
          img: ({ src, alt }) => (
            <img src={src} alt={alt || ''} className="readme-img" loading="lazy" />
          ),
          strong: ({ children }) => (
            <strong className="readme-strong">{children}</strong>
          ),
        }}
      >
        {content}
      </Markdown>
    </article>
  )
}

/* ── Main Component ─────────────────────────────── */

export function ArchitectureReport({ jobId }: Props) {
  const [diagram, setDiagram] = useState<DiagramData | null>(null)
  const [report, setReport] = useState<any>(null)
  const [tab, setTab] = useState<Tab>('graph')

  // README state
  const [readme, setReadme] = useState<string | null>(null)
  const [readmeSource, setReadmeSource] = useState<string | null>(null)
  const [readmeLoading, setReadmeLoading] = useState(false)
  const [readmeFetched, setReadmeFetched] = useState(false)
  const [readmeLang, setReadmeLang] = useState('en')

  useEffect(() => {
    getDiagram(jobId).then(setDiagram).catch(() => {})
    getReport(jobId).then(setReport).catch(() => {})
  }, [jobId])

  const fetchReadme = useCallback(() => {
    setReadmeLoading(true)
    getReadme(jobId)
      .then(data => {
        setReadme(data.content)
        setReadmeSource(data.source)
        setReadmeFetched(true)
      })
      .catch(() => {
        setReadme(null)
        setReadmeFetched(true)
      })
      .finally(() => setReadmeLoading(false))
  }, [jobId])

  const handleGenerate = useCallback(async () => {
    setReadmeLoading(true)
    setReadme('')
    setReadmeSource(null)
    try {
      await streamGenerateReadme(jobId, {
        onToken: (token) => {
          setReadme(prev => prev + token)
        },
        onDone: (source) => {
          setReadmeSource(source)
          setReadmeLoading(false)
        },
        onError: () => {
          setReadmeLoading(false)
        },
      }, { language: readmeLang })
    } catch {
      setReadmeLoading(false)
    }
  }, [jobId, readmeLang])

  useEffect(() => {
    if (tab === 'readme' && !readmeFetched) fetchReadme()
  }, [tab, readmeFetched, fetchReadme])

  const m = report?.manifest

  return (
    <section className="bg-[var(--bg-card)] rounded-lg border border-[var(--border)] p-6 shadow-sm fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
        <div>
          <h2 className="text-[16px] font-semibold text-[var(--text)] mb-0.5 tracking-tight">Architecture</h2>
          <p className="text-[13px] text-[var(--text-muted)]">Graphe de dépendances et modules</p>
        </div>
        {diagram && (
           <span className="text-[12px] font-medium text-[var(--text-secondary)] bg-[var(--bg-subtle)] border border-[var(--border)] px-2.5 py-1 rounded-md self-start sm:self-auto font-mono">
             {diagram.detected_pattern}
           </span>
        )}
      </div>

      {/* Stats */}
      {m && (
        <div className="flex items-center gap-6 mb-6">
          {[
            { v: m.total_files, l: 'Fichiers', t: 'Nombre total de fichiers source analysés dans le dépôt' },
            { v: m.total_lines?.toLocaleString(), l: 'Lignes', t: 'Nombre total de lignes de code (LOC) du projet' },
            { v: m.languages?.length ?? 0, l: 'Langages', t: 'Nombre de langages de programmation différents détectés' },
            { v: diagram?.module_count ?? 0, l: 'Modules', t: 'Nombre de modules (fichiers ou dossiers) dans le graphe de dépendances' },
          ].map(({ v, l, t }) => (
            <Tooltip key={l} text={t}>
              <div className="flex items-baseline gap-2 cursor-help">
                <div className="text-[15px] font-semibold text-[var(--text)] tabular-nums">{v}</div>
                <div className="text-[12px] text-[var(--text-muted)]">{l}</div>
              </div>
            </Tooltip>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-6 border-b border-[var(--border)] mb-5">
        {([
          { key: 'graph' as Tab, label: 'Architecture' },
          { key: 'readme' as Tab, label: 'README' },
          { key: 'info' as Tab, label: 'Détails' },
        ]).map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`pb-2.5 text-[13px] font-medium transition-colors border-b-2 -mb-[1px] ${
              tab === key
                ? 'border-[var(--color-primary)] text-[var(--text)]'
                : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text)]'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-[300px]">
        {/* ── Architecture Tab ── */}
        {tab === 'graph' && (
          <div className="space-y-5">
            {diagram ? (
              <>
                {diagram.diagram && (
                  <MermaidDiagram diagram={diagram.diagram} />
                )}

                {/* Insight Grid — forced horizontal scroll */}
                <div className="flex gap-5 overflow-x-auto pb-2" style={{ scrollbarWidth: 'thin' }}>
                  {/* Pattern */}
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-6 min-w-[320px] flex-1">
                    <div className="flex items-center gap-3 mb-4">
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-[var(--text-muted)]">
                        <rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/>
                        <rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/>
                        <rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/>
                        <rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/>
                      </svg>
                      <Tooltip text="Le pattern architectural décrit la façon dont le code est organisé (ex: MVC, monolith, microservices, layered). Il est déduit de la structure des dossiers et des dépendances.">
                        <span className="text-[13px] font-semibold uppercase tracking-wider text-[var(--text-muted)] cursor-help underline decoration-dotted decoration-[var(--border-strong)] underline-offset-4">Pattern</span>
                      </Tooltip>
                    </div>
                    <span className="text-[18px] font-semibold text-[var(--text)] capitalize">{diagram.detected_pattern}</span>
                  </div>

                  {/* Entry Points */}
                  <InsightCard
                    icon={
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
                        <path d="M8 5v3l2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    }
                    label="Points d'entrée"
                    tooltip="Les points d'entrée sont les fichiers ou fonctions par lesquels l'exécution du programme démarre (ex: main(), app.listen(), index.ts). Ce sont les portes d'entrée du code."
                    items={diagram.entry_points}
                  />

                  {/* Core Modules */}
                  <InsightCard
                    icon={
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <path d="M8 1l6 3.5v6L8 14 2 10.5v-6L8 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                      </svg>
                    }
                    label="Modules core"
                    tooltip="Les modules core sont les fichiers les plus connectés du projet — ils sont importés par beaucoup d'autres modules. Ce sont les pièces centrales de l'architecture."
                    items={diagram.core_modules}
                  />

                  {/* Orphan Modules */}
                  <InsightCard
                    icon={
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
                        <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    }
                    label="Modules orphelins"
                    tooltip="Les modules orphelins ne sont importés par aucun autre fichier du projet. Ils pourraient être du code mort, des utilitaires non utilisés, ou des fichiers en attente d'intégration."
                    items={diagram.orphan_modules}
                  />
                </div>

                {/* Cycles warning */}
                {diagram.dependency_cycles?.length > 0 && (
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-[var(--text-muted)]">
                        <path d="M8 1a7 7 0 100 14A7 7 0 008 1z" stroke="currentColor" strokeWidth="1.5"/>
                        <path d="M8 5v3l2 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                      <Tooltip text="Un cycle de dépendance signifie que le module A dépend de B qui dépend de A (directement ou indirectement). Cela rend le code difficile à comprendre et peut causer des bugs.">
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] cursor-help underline decoration-dotted decoration-[var(--border-strong)] underline-offset-4">
                          Cycles de dépendances
                        </span>
                      </Tooltip>
                      <span className="text-[10px] tabular-nums text-[var(--text-faint)] bg-[var(--bg-subtle)] px-1.5 py-0.5 rounded-full font-medium">
                        {diagram.dependency_cycles.length}
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {diagram.dependency_cycles.slice(0, 5).map((c, i) => (
                        <div key={i} className="text-[11px] font-mono text-[var(--text-secondary)] bg-[var(--bg-subtle)] px-2.5 py-1.5 rounded-md border border-[var(--border)] flex items-center gap-2">
                          {c.map((node, j) => (
                            <span key={j} className="flex items-center gap-2">
                              {j > 0 && <span className="text-[var(--text-faint)]">&rarr;</span>}
                              <span className="truncate">{node}</span>
                            </span>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex items-center justify-center h-[300px] text-[var(--text-faint)] text-[13px]">
                Chargement de l'architecture...
              </div>
            )}
          </div>
        )}

        {/* ── README Tab ── */}
        {tab === 'readme' && (
          <div>
            {/* Language selector + regenerate */}
            {readmeFetched && !readmeLoading && readme === null && (
              <div className="flex items-center gap-3 mb-4">
                <select
                  value={readmeLang}
                  onChange={e => setReadmeLang(e.target.value)}
                  className="text-[12px] font-medium text-[var(--text-secondary)] bg-[var(--bg-subtle)] border border-[var(--border)] rounded-md px-2.5 py-1.5 focus:outline-none focus:border-[var(--text-faint)] transition-colors cursor-pointer appearance-none pr-7"
                  style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg width=\'10\' height=\'6\' viewBox=\'0 0 10 6\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cpath d=\'M1 1l4 4 4-4\' stroke=\'%23737373\' stroke-width=\'1.5\' fill=\'none\' stroke-linecap=\'round\' stroke-linejoin=\'round\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 8px center' }}
                >
                  <option value="en">English</option>
                  <option value="fr">Français</option>
                  <option value="es">Español</option>
                  <option value="de">Deutsch</option>
                  <option value="pt">Português</option>
                  <option value="it">Italiano</option>
                  <option value="ja">日本語</option>
                  <option value="zh">中文</option>
                </select>
              </div>
            )}

            {readme !== null && readme !== '' && !readmeLoading && (
              <div className="flex items-center gap-3 mb-4">
                <select
                  value={readmeLang}
                  onChange={e => setReadmeLang(e.target.value)}
                  className="text-[12px] font-medium text-[var(--text-secondary)] bg-[var(--bg-subtle)] border border-[var(--border)] rounded-md px-2.5 py-1.5 focus:outline-none focus:border-[var(--text-faint)] transition-colors cursor-pointer appearance-none pr-7"
                  style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg width=\'10\' height=\'6\' viewBox=\'0 0 10 6\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cpath d=\'M1 1l4 4 4-4\' stroke=\'%23737373\' stroke-width=\'1.5\' fill=\'none\' stroke-linecap=\'round\' stroke-linejoin=\'round\'/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 8px center' }}
                >
                  <option value="en">English</option>
                  <option value="fr">Français</option>
                  <option value="es">Español</option>
                  <option value="de">Deutsch</option>
                  <option value="pt">Português</option>
                  <option value="it">Italiano</option>
                  <option value="ja">日本語</option>
                  <option value="zh">中文</option>
                </select>
                <button
                  onClick={handleGenerate}
                  className="text-[12px] font-medium text-[var(--text-muted)] bg-[var(--bg-subtle)] border border-[var(--border)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)] px-3 py-1.5 rounded-md transition-colors"
                >
                  Régénérer
                </button>
              </div>
            )}

            {readmeLoading && readme === '' && (
              <div className="flex flex-col items-center justify-center h-[400px] gap-3">
                <span className="w-5 h-5 border-2 border-[var(--border)] border-t-[var(--accent)] rounded-full animate-spin" />
                <span className="text-[13px] text-[var(--text-faint)]">
                  {readmeFetched ? 'Génération en cours...' : 'Chargement...'}
                </span>
              </div>
            )}
            {readme !== null && readme !== '' && (
              <div className="readme-container">
                {readmeLoading && (
                  <div className="flex items-center gap-2 mb-4">
                    <span className="w-1.5 h-1.5 bg-[var(--color-primary)] rounded-full animate-pulse" />
                    <span className="text-[12px] text-[var(--color-primary)] font-medium">Génération en cours...</span>
                  </div>
                )}
                {!readmeLoading && readmeSource === 'generated' && (
                  <div className="flex items-center gap-2 mb-4">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-[var(--color-success)]">
                      <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.5"/>
                      <path d="M4 6l1.5 1.5L8 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                    <span className="text-[12px] text-[var(--color-success)] font-medium">Généré avec succès</span>
                  </div>
                )}
                {readmeSource && (
                  <div className="mb-5">
                    <span className={`inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md border ${
                      readmeSource === 'repo'
                        ? 'bg-[var(--color-success-bg)] text-[var(--color-success)] border-[var(--color-success-border)]'
                        : 'bg-[var(--color-primary-bg)] text-[var(--color-primary)] border-[var(--color-primary-border)]'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        readmeSource === 'repo' ? 'bg-[var(--color-success)]' : 'bg-[var(--color-primary)]'
                      }`} />
                      {readmeSource === 'repo' ? 'README du dépôt' : 'Généré par IA'}
                    </span>
                  </div>
                )}
                <ReadmeRenderer content={readme} />
              </div>
            )}
            {!readmeLoading && readme === null && readmeFetched && (
              <div className="flex flex-col items-center justify-center h-[400px] gap-4">
                <div className="w-12 h-12 rounded-xl bg-[var(--bg-subtle)] border border-[var(--border)] flex items-center justify-center mb-1">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="text-[var(--text-faint)]">
                    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                    <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                <span className="text-[14px] text-[var(--text-muted)] font-medium">Aucun README trouvé</span>
                <span className="text-[13px] text-[var(--text-faint)]">Ce dépôt ne contient pas de fichier README.</span>
                <button
                  onClick={handleGenerate}
                  className="mt-1 text-[13px] font-medium text-[var(--accent-text)] bg-[var(--accent)] hover:bg-[var(--accent-hover)] px-5 py-2.5 rounded-lg transition-colors shadow-xs"
                >
                  Générer un README
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Details Tab ── */}
        {tab === 'info' && diagram && (
          <div className="space-y-6 animate-in fade-in">
            {m?.languages?.length > 0 && (
              <div>
                <h3 className="text-[13px] font-semibold text-[var(--text)] mb-2.5">Langages</h3>
                <div className="flex flex-wrap gap-2">
                  {m.languages.map((l: any) => (
                    <div key={l.name} className="flex items-center gap-2 px-2.5 py-1.5 bg-[var(--bg-card)] rounded-md border border-[var(--border)] shadow-xs">
                      <span className="font-medium text-[var(--text)] text-[12px]">{l.name}</span>
                      <span className="text-[11px] font-mono text-[var(--text-muted)]">
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
                  <h3 className="text-[13px] font-semibold text-[var(--text)] mb-2.5">Modules Core</h3>
                  <div className="flex flex-wrap gap-2">
                    {diagram.core_modules.map((mod: string) => (
                      <span key={mod} className="text-[11px] font-mono px-2 py-1 bg-[var(--bg-subtle)] text-[var(--text)] border border-[var(--border)] rounded-md">
                        {mod}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {diagram.orphan_modules?.length > 0 && (
                <div>
                  <h3 className="text-[13px] font-semibold text-[var(--text)] mb-2.5">Modules orphelins</h3>
                  <div className="flex flex-wrap gap-2">
                    {diagram.orphan_modules.map((mod: string) => (
                      <span key={mod} className="text-[11px] font-mono px-2 py-1 bg-[var(--bg-card)] text-[var(--text-muted)] border border-[var(--border)] rounded-md">
                        {mod}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {diagram.dependency_cycles?.length > 0 && (
              <div className="p-3 bg-[var(--bg-card)] border border-[var(--border)] rounded-md">
                <h3 className="text-[13px] font-semibold text-[var(--text)] mb-2">
                  Cycles de dépendances ({diagram.dependency_cycles.length})
                </h3>
                <div className="space-y-1.5">
                  {diagram.dependency_cycles.slice(0, 5).map((c: string[], i: number) => (
                    <div key={i} className="text-[11px] font-mono text-[var(--text-secondary)] bg-[var(--bg-subtle)] px-2 py-1 rounded border border-[var(--border)] truncate">
                      {c.join(' \u2194 ')}
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
