import { useEffect, useRef, useId, useState } from 'react'
import mermaid from 'mermaid'

interface MermaidDiagramProps {
  diagram: string
}

let initDone = false

function initMermaid(isDark: boolean) {
  mermaid.initialize({
    startOnLoad: false,
    theme: isDark ? 'dark' : 'neutral',
    flowchart: {
      useMaxWidth: true,
      htmlLabels: true,
      curve: 'basis',
    },
    themeVariables: {
      fontFamily: '"Inter", ui-sans-serif, system-ui, sans-serif',
      fontSize: '13px',
      ...(isDark
        ? { primaryColor: '#1e1b4b', primaryTextColor: '#e0e7ff', primaryBorderColor: '#6366f1', lineColor: '#404040', secondaryColor: '#141414', tertiaryColor: '#1c1c1c' }
        : { primaryColor: '#f5f5f5', primaryTextColor: '#404040', primaryBorderColor: '#d4d4d8', lineColor: '#a3a3a3', secondaryColor: '#ffffff', tertiaryColor: '#fafafa' }),
    },
  })
  initDone = true
}

export function MermaidDiagram({ diagram }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const uniqueId = useId().replace(/:/g, '_')
  const [error, setError] = useState<string | null>(null)
  const renderCount = useRef(0)

  useEffect(() => {
    if (!diagram) return

    if (!initDone) {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
      initMermaid(isDark)
    }

    const renderId = `mermaid-${uniqueId}-${++renderCount.current}`
    setError(null)

    async function render() {
      try {
        // Remove any previous mermaid error elements
        const prev = document.getElementById('d' + renderId)
        if (prev) prev.remove()

        containerRef.current!.innerHTML = ''
        const { svg } = await mermaid.render(renderId, diagram)
        if (containerRef.current) {
          containerRef.current.innerHTML = svg
        }
      } catch (e) {
        console.warn('[MermaidDiagram] Render failed:', e)
        setError('Erreur de rendu du diagramme')
      }
    }

    render()
  }, [diagram, uniqueId])

  // Theme reactivity
  useEffect(() => {
    const observer = new MutationObserver(() => {
      if (!diagram) return
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
      initMermaid(isDark)
      // Force re-render
      const renderId = `mermaid-${uniqueId}-${++renderCount.current}`
      mermaid.render(renderId, diagram).then(({ svg }) => {
        if (containerRef.current) containerRef.current.innerHTML = svg
      }).catch(() => {})
    })

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })

    return () => observer.disconnect()
  }, [diagram, uniqueId])

  if (!diagram) {
    return (
      <div className="mermaid-container rounded-lg border border-[var(--border)] overflow-hidden flex items-center justify-center" style={{ minHeight: 300 }}>
        <span className="text-[var(--text-faint)] text-[13px]">Chargement du diagramme...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="mermaid-container rounded-lg border border-[var(--border)] overflow-hidden" style={{ minHeight: 300 }}>
        <div className="flex items-center justify-center h-full" style={{ minHeight: 300 }}>
          <div className="text-center">
            <span className="text-[var(--text-faint)] text-[13px]">{error}</span>
            <pre className="mt-3 text-[11px] text-[var(--text-muted)] bg-[var(--bg-subtle)] p-4 rounded-lg border border-[var(--border)] text-left max-w-[600px] mx-auto overflow-auto max-h-[200px]">{diagram}</pre>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="mermaid-container rounded-lg border border-[var(--border)] overflow-hidden"
      style={{ minHeight: 300, width: '100%' }}
    />
  )
}
