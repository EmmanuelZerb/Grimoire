import { useEffect, useState, useRef, useCallback } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import mermaid from 'mermaid'
import { getDiagram, getReport, getReadme, generateReadme } from '../lib/api'

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

function initMermaid(theme: 'light' | 'dark') {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'base',
    themeVariables: {
      primaryColor: theme === 'dark' ? '#1c1c1c' : '#f5f5f5',
      primaryTextColor: theme === 'dark' ? '#e5e5e5' : '#171717',
      primaryBorderColor: theme === 'dark' ? '#333333' : '#d4d4d4',
      lineColor: theme === 'dark' ? '#525252' : '#a3a3a3',
      secondaryColor: theme === 'dark' ? '#141414' : '#fafafa',
      tertiaryColor: theme === 'dark' ? '#262626' : '#eaeaea',
      fontSize: '18px',
      fontFamily: '"JetBrains Mono", ui-monospace, monospace',
    },
    flowchart: {
      htmlLabels: true,
      curve: 'basis',
      padding: 24,
      nodeSpacing: 50,
      rankSpacing: 60,
      rankDirection: 'LR',
      useMaxWidth: false,
      defaultRenderer: 'dagre',
    },
    theme: 'base',
  })
}

/* ── Mermaid Diagram Renderer ────────────────────── */

function MermaidDiagram({ source }: { source: string }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const resizeRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [showRight, setShowRight] = useState(false)
  const [showLeft, setShowLeft] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [height, setHeight] = useState(180)

  useEffect(() => {
    if (!source || !containerRef.current) return
    const id = `mermaid-${Math.random().toString(36).slice(2, 9)}`
    let cancelled = false

    const theme = (document.documentElement.getAttribute('data-theme') || 'light') as 'light' | 'dark'
    initMermaid(theme)

    // Force horizontal layout: always use flowchart LR with dagre renderer
    const dagreDirective = "%%{init: {'flowchart': {'defaultRenderer': 'dagre', 'rankDirection': 'LR'}}}%%"
    const forcedSource = source
      .replace(/^%%\{.*?%%\n?/m, '')
      .replace(/^graph\s+(LR|TD|TB|BT|RL)/m, 'flowchart LR')
      .replace(/^flowchart\s+(TD|TB|BT|RL)/m, 'flowchart LR')
    const finalSource = `${dagreDirective}\n${forcedSource}`

    mermaid.render(id, finalSource).then(
      ({ svg }) => {
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg
          requestAnimationFrame(() => {
            if (scrollRef.current) checkOverflow()
          })
        }
      },
      (err) => {
        if (!cancelled) setError(String(err))
      }
    )

    return () => { cancelled = true }
  }, [source])

  const checkOverflow = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    setShowRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4)
    setShowLeft(el.scrollLeft > 4)
  }, [])

  const scroll = useCallback((direction: 'left' | 'right') => {
    const el = scrollRef.current
    if (!el) return
    const amount = el.clientWidth * 0.6
    el.scrollBy({ left: direction === 'right' ? amount : -amount, behavior: 'smooth' })
  }, [])

  const zoomIn = useCallback(() => setZoom(z => Math.min(z + 0.25, 4)), [])
  const zoomOut = useCallback(() => setZoom(z => Math.max(z - 0.25, 0.25)), [])
  const resetZoom = useCallback(() => setZoom(1), [])

  // Resize handle drag
  const handleResizeMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const startY = e.clientY
    const startH = height
    const onMove = (ev: MouseEvent) => {
      const delta = ev.clientY - startY
      setHeight(Math.max(120, Math.min(startH + delta, 800)))
    }
    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.body.style.cursor = 'se-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [height])

  // Scroll wheel zoom
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      setZoom(z => {
        const delta = e.deltaY > 0 ? -0.15 : 0.15
        return Math.min(Math.max(z + delta, 0.25), 4)
      })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  // Click-drag pan
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    let isDown = false
    let startX = 0
    let startY = 0
    let scrollX = 0
    let scrollY = 0

    const onMouseDown = (e: MouseEvent) => {
      isDown = true
      startX = e.pageX - el.offsetLeft
      startY = e.pageY - el.offsetTop
      scrollX = el.scrollLeft
      scrollY = el.scrollTop
      el.style.cursor = 'grabbing'
    }
    const onMouseUp = () => {
      isDown = false
      el.style.cursor = 'grab'
    }
    const onMouseLeave = () => {
      isDown = false
      el.style.cursor = 'grab'
    }
    const onMouseMove = (e: MouseEvent) => {
      if (!isDown) return
      e.preventDefault()
      const x = e.pageX - el.offsetLeft
      const y = e.pageY - el.offsetTop
      el.scrollLeft = scrollX - (x - startX)
      el.scrollTop = scrollY - (y - startY)
    }

    el.style.cursor = 'grab'
    el.addEventListener('mousedown', onMouseDown)
    el.addEventListener('mouseup', onMouseUp)
    el.addEventListener('mouseleave', onMouseLeave)
    el.addEventListener('mousemove', onMouseMove)
    return () => {
      el.removeEventListener('mousedown', onMouseDown)
      el.removeEventListener('mouseup', onMouseUp)
      el.removeEventListener('mouseleave', onMouseLeave)
      el.removeEventListener('mousemove', onMouseMove)
    }
  }, [])

  if (error) return null

  return (
    <div className="relative group/diagram">
      <div
        ref={scrollRef}
        onScroll={checkOverflow}
        className="bg-[var(--bg-subtle)] border border-[var(--border)] rounded-lg overflow-auto"
        style={{ height }}
      >
        <div
          ref={containerRef}
          className="mermaid-wrap flex justify-start px-6 py-4"
          style={{ minWidth: 'max-content', transform: `scale(${zoom})`, transformOrigin: 'top left', transition: 'transform 0.15s ease' }}
        />
      </div>

      {/* Scroll arrows */}
      {showLeft && (
        <button
          onClick={() => scroll('left')}
          className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-[var(--bg-card)] border border-[var(--border)] shadow-md flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text)] hover:border-[var(--border-strong)] transition-all opacity-0 group-hover/diagram:opacity-100 z-10"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M8.5 3L4.5 7L8.5 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </button>
      )}
      {showRight && (
        <button
          onClick={() => scroll('right')}
          className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-[var(--bg-card)] border border-[var(--border)] shadow-md flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text)] hover:border-[var(--border-strong)] transition-all opacity-0 group-hover/diagram:opacity-100 z-10"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M5.5 3L9.5 7L5.5 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </button>
      )}

      {/* Bottom resize handle */}
      <div
        ref={resizeRef}
        onMouseDown={handleResizeMouseDown}
        className="absolute bottom-0 right-0 w-6 h-6 cursor-se-resize flex items-end justify-end pb-1 pr-1 z-10"
        title="Redimensionner"
      >
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="text-[var(--text-faint)] opacity-60 group-hover/diagram:opacity-100 transition-opacity">
          <path d="M9 1v8H1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          <path d="M6 4l3 3M4 6l5 5" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/>
        </svg>
      </div>
    </div>
  )
}

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
  variant = 'default',
}: {
  icon: React.ReactNode
  label: string
  tooltip: string
  items: string[]
  variant?: 'default' | 'warning'
}) {
  if (items.length === 0) return null
  const colors = variant === 'warning'
    ? 'border-orange-200 bg-orange-50/30'
    : 'border-[var(--border)] bg-[var(--bg-card)]'
  return (
    <div className={`rounded-lg border p-4 ${colors}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className={variant === 'warning' ? 'text-orange-500' : 'text-[var(--text-muted)]'}>{icon}</span>
        <Tooltip text={tooltip}>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] cursor-help underline decoration-dotted decoration-[var(--border-strong)] underline-offset-4">{label}</span>
        </Tooltip>
        <span className="text-[10px] tabular-nums text-[var(--text-faint)] bg-[var(--bg-subtle)] px-1.5 py-0.5 rounded-full font-medium">
          {items.length}
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item}
            className={`text-[11px] font-mono px-2 py-1 rounded-md border truncate max-w-full ${
              variant === 'warning'
                ? 'bg-[var(--bg-card)] text-orange-700 border-orange-200'
                : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] border-[var(--border)]'
            }`}
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
    try {
      const data = await generateReadme(jobId)
      setReadme(data.content)
      setReadmeSource(data.source)
    } catch (err) {
      console.error('README generation failed:', err)
    } finally {
      setReadmeLoading(false)
    }
  }, [jobId])

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
                ? 'border-[var(--accent)] text-[var(--text)]'
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
                {diagram.diagram && <MermaidDiagram source={diagram.diagram} />}

                {/* Insight Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Pattern */}
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-card)] p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-[var(--text-muted)]">
                        <rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/>
                        <rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/>
                        <rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/>
                        <rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/>
                      </svg>
                      <Tooltip text="Le pattern architectural décrit la façon dont le code est organisé (ex: MVC, monolith, microservices, layered). Il est déduit de la structure des dossiers et des dépendances.">
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)] cursor-help underline decoration-dotted decoration-[var(--border-strong)] underline-offset-4">Pattern</span>
                      </Tooltip>
                    </div>
                    <span className="text-[15px] font-semibold text-[var(--text)] capitalize">{diagram.detected_pattern}</span>
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
                    variant="warning"
                  />
                </div>

                {/* Cycles warning */}
                {diagram.dependency_cycles?.length > 0 && (
                  <div className="rounded-lg border border-red-200 bg-red-50/40 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="text-red-500">
                        <path d="M8 1a7 7 0 100 14A7 7 0 008 1z" stroke="currentColor" strokeWidth="1.5"/>
                        <path d="M8 5v3l2 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                      <Tooltip text="Un cycle de dépendance signifie que le module A dépend de B qui dépend de A (directement ou indirectement). Cela rend le code difficile à comprendre et peut causer des bugs.">
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-red-600 cursor-help underline decoration-dotted decoration-red-200 underline-offset-4">
                          Cycles de dépendances
                        </span>
                      </Tooltip>
                      <span className="text-[10px] tabular-nums text-red-500 bg-red-100 px-1.5 py-0.5 rounded-full font-medium">
                        {diagram.dependency_cycles.length}
                      </span>
                    </div>
                    <div className="space-y-1.5">
                      {diagram.dependency_cycles.slice(0, 5).map((c, i) => (
                        <div key={i} className="text-[11px] font-mono text-red-700 bg-[var(--bg-card)] px-2.5 py-1.5 rounded-md border border-red-200 flex items-center gap-2">
                          {c.map((node, j) => (
                            <span key={j} className="flex items-center gap-2">
                              {j > 0 && <span className="text-red-300">&rarr;</span>}
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
            {readmeLoading && (
              <div className="flex flex-col items-center justify-center h-[400px] gap-3">
                <span className="w-5 h-5 border-2 border-[var(--border)] border-t-[var(--accent)] rounded-full animate-spin" />
                <span className="text-[13px] text-[var(--text-faint)]">
                  {readmeFetched ? 'Génération en cours...' : 'Chargement...'}
                </span>
              </div>
            )}
            {!readmeLoading && readme && (
              <div className="readme-container">
                {readmeSource && (
                  <div className="mb-5">
                    <span className={`inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md border ${
                      readmeSource === 'repo'
                        ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20'
                        : 'bg-sky-500/10 text-sky-600 border-sky-500/20'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        readmeSource === 'repo' ? 'bg-emerald-500' : 'bg-sky-400'
                      }`} />
                      {readmeSource === 'repo' ? 'README du dépôt' : 'Généré par IA'}
                    </span>
                  </div>
                )}
                <ReadmeRenderer content={readme} />
              </div>
            )}
            {!readmeLoading && !readme && readmeFetched && (
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
              <div className="p-3 bg-[var(--bg-card)] border border-red-200 rounded-md">
                <h3 className="text-[13px] font-semibold text-red-600 mb-2">
                  Cycles de dépendances ({diagram.dependency_cycles.length})
                </h3>
                <div className="space-y-1.5">
                  {diagram.dependency_cycles.slice(0, 5).map((c: string[], i: number) => (
                    <div key={i} className="text-[11px] font-mono text-red-600 bg-red-50 px-2 py-1 rounded border border-red-100 truncate">
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
