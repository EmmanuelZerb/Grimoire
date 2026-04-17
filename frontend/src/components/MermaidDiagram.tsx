import { useEffect, useRef, useId, useState, useCallback } from 'react'
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
      useMaxWidth: false,
      htmlLabels: false,
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

const DEFAULT_HEIGHT = 380
const MIN_HEIGHT = 200
const MAX_HEIGHT = 900
const PAN_STEP = 200
const ZOOM_STEP = 0.12
const MIN_ZOOM = 0.3
const MAX_ZOOM = 4
const INITIAL_ZOOM = 1

/** Smooth animation via requestAnimationFrame with ease-out cubic. */
function smoothPan(
  fromX: number, fromY: number,
  toX: number, toY: number,
  duration: number,
  onFrame: (x: number, y: number) => void,
) {
  const start = performance.now()
  function tick(now: number) {
    const t = Math.min((now - start) / duration, 1)
    const ease = 1 - Math.pow(1 - t, 3)
    onFrame(fromX + (toX - fromX) * ease, fromY + (toY - fromY) * ease)
    if (t < 1) requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}

export function MermaidDiagram({ diagram }: MermaidDiagramProps) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement | null>(null)
  const uniqueId = useId().replace(/:/g, '_')
  const [error, setError] = useState<string | null>(null)
  const renderCount = useRef(0)

  // View state
  const zoom = useRef(INITIAL_ZOOM)
  const panX = useRef(0)
  const panY = useRef(0)
  const isPanning = useRef(false)
  const lastMouse = useRef({ x: 0, y: 0 })

  const [height, setHeight] = useState(DEFAULT_HEIGHT)
  const isResizing = useRef(false)
  const resizeStartY = useRef(0)
  const resizeStartH = useRef(0)

  /** Apply zoom & pan via CSS transform — keeps the diagram centered. */
  const applyTransform = useCallback(() => {
    const svg = svgRef.current
    if (!svg) return
    svg.style.transform = `translate(-50%, -50%) translate(${panX.current}px, ${panY.current}px) scale(${zoom.current})`
    svg.style.transformOrigin = 'center center'
    svg.style.position = 'absolute'
    svg.style.left = '50%'
    svg.style.top = '50%'
  }, [])

  // Reset on diagram change
  useEffect(() => {
    panX.current = 0
    panY.current = 0
    zoom.current = INITIAL_ZOOM
    applyTransform()
  }, [diagram, applyTransform])

  // Wheel zoom
  useEffect(() => {
    const vp = viewportRef.current
    if (!vp || !diagram || error) return

    function onWheel(e: WheelEvent) {
      e.preventDefault()
      const oldZoom = zoom.current
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP
      zoom.current = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, oldZoom + delta))
      applyTransform()
    }

    vp.addEventListener('wheel', onWheel, { passive: false })
    return () => vp.removeEventListener('wheel', onWheel)
  }, [diagram, error, applyTransform])

  // Pan with left-click drag
  useEffect(() => {
    const vp = viewportRef.current
    if (!vp || !diagram || error) return

    function onMouseDown(e: MouseEvent) {
      if (e.button !== 0) return
      const target = e.target as HTMLElement
      if (target.closest('button') || target.closest('.resize-handle')) return
      e.preventDefault()
      isPanning.current = true
      lastMouse.current = { x: e.clientX, y: e.clientY }
    }

    function onMouseMove(e: MouseEvent) {
      if (isResizing.current) return
      if (!isPanning.current) return
      panX.current += e.clientX - lastMouse.current.x
      panY.current += e.clientY - lastMouse.current.y
      lastMouse.current = { x: e.clientX, y: e.clientY }
      applyTransform()
    }

    function onMouseUp() {
      isPanning.current = false
    }

    vp.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      vp.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [diagram, error, applyTransform])

  // Resize handle drag
  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      if (!isResizing.current) return
      const delta = e.clientY - resizeStartY.current
      const newH = Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, resizeStartH.current + delta))
      setHeight(newH)
    }

    function onMouseUp() {
      isResizing.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [])

  const smoothPanTo = useCallback((dx: number, dy: number) => {
    const fromX = panX.current
    const fromY = panY.current
    smoothPan(fromX, fromY, fromX + dx, fromY + dy, 350, (x, y) => {
      panX.current = x
      panY.current = y
      applyTransform()
    })
  }, [applyTransform])

  const resetView = useCallback(() => {
    const fromX = panX.current
    const fromY = panY.current
    const fromZ = zoom.current
    const start = performance.now()
    const duration = 350
    function tick(now: number) {
      const t = Math.min((now - start) / duration, 1)
      const ease = 1 - Math.pow(1 - t, 3)
      panX.current = fromX * (1 - ease)
      panY.current = fromY * (1 - ease)
      zoom.current = fromZ + (INITIAL_ZOOM - fromZ) * ease
      applyTransform()
      if (t < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, [applyTransform])

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    isResizing.current = true
    resizeStartY.current = e.clientY
    resizeStartH.current = height
    document.body.style.cursor = 'ns-resize'
    document.body.style.userSelect = 'none'
  }, [height])

  // Mermaid render
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
        const prev = document.getElementById('d' + renderId)
        if (prev) prev.remove()

        const container = viewportRef.current!
        container.innerHTML = ''
        const { svg } = await mermaid.render(renderId, diagram)
        container.innerHTML = svg

        const svgEl = container.querySelector('svg') as SVGSVGElement | null
        if (svgEl) {
          svgRef.current = svgEl
          svgEl.style.maxWidth = 'none'
          svgEl.style.overflow = 'visible'
          applyTransform()
        }
      } catch (e) {
        console.warn('[MermaidDiagram] Render failed:', e)
        setError('Erreur de rendu du diagramme')
      }
    }

    render()
  }, [diagram, uniqueId, applyTransform])

  // Theme reactivity
  useEffect(() => {
    const observer = new MutationObserver(() => {
      if (!diagram) return
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
      initMermaid(isDark)
      const renderId = `mermaid-${uniqueId}-${++renderCount.current}`
      mermaid.render(renderId, diagram).then(({ svg }) => {
        if (viewportRef.current) {
          viewportRef.current.innerHTML = svg
          const svgEl = viewportRef.current.querySelector('svg') as SVGSVGElement | null
          if (svgEl) {
            svgRef.current = svgEl
            svgEl.style.maxWidth = 'none'
            svgEl.style.overflow = 'visible'
            applyTransform()
          }
        }
      }).catch(() => {})
    })

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })

    return () => observer.disconnect()
  }, [diagram, uniqueId, applyTransform])

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
    <div className="mermaid-container rounded-lg border border-[var(--border)] overflow-hidden relative group/diagram">
      {/* Viewport */}
      <div
        ref={viewportRef}
        className="overflow-hidden w-full relative"
        style={{ height, cursor: 'default' }}
      />

      {/* Top bar: zoom indicator + reset */}
      <div className="absolute top-3 left-3 flex items-center gap-2 z-10 opacity-0 group-hover/diagram:opacity-100 transition-opacity">
        <span className="text-[10px] font-mono text-[var(--text-faint)] bg-[var(--bg-card)]/90 backdrop-blur-sm border border-[var(--border)] px-2 py-1 rounded-md tabular-nums">
          {Math.round(zoom.current * 100)}%
        </span>
        <button
          onClick={resetView}
          className="w-7 h-7 rounded-md bg-[var(--bg-card)]/90 backdrop-blur-sm border border-[var(--border)] flex items-center justify-center text-[var(--text-faint)] hover:text-[var(--text-muted)] transition-colors pointer-events-auto"
          title="Réinitialiser la vue"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M1 5h1M10 5h1M6 1v1M6 10v1M2.5 2.5l.7.7M8.8 8.8l.7.7M2.5 9.5l.7-.7M8.8 3.2l.7-.7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
          </svg>
        </button>
      </div>

      {/* Left arrow */}
      <div className="absolute top-1/2 -translate-y-1/2 left-3 z-10 opacity-0 group-hover/diagram:opacity-100 transition-opacity">
        <button
          onClick={() => smoothPanTo(PAN_STEP, 0)}
          className="w-9 h-9 rounded-full bg-[var(--bg-card)]/90 backdrop-blur-sm border border-[var(--border)] flex items-center justify-center text-[var(--text-faint)] hover:text-[var(--text)] hover:border-[var(--border-strong)] hover:shadow-sm active:scale-90 transition-all duration-200 pointer-events-auto"
          title="Défiler à gauche"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M8.5 3L5 7l3.5 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>

      {/* Right arrow */}
      <div className="absolute top-1/2 -translate-y-1/2 right-3 z-10 opacity-0 group-hover/diagram:opacity-100 transition-opacity">
        <button
          onClick={() => smoothPanTo(-PAN_STEP, 0)}
          className="w-9 h-9 rounded-full bg-[var(--bg-card)]/90 backdrop-blur-sm border border-[var(--border)] flex items-center justify-center text-[var(--text-faint)] hover:text-[var(--text)] hover:border-[var(--border-strong)] hover:shadow-sm active:scale-90 transition-all duration-200 pointer-events-auto"
          title="Défiler à droite"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M5.5 3L9 7l-3.5 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>

      {/* Resize handle (bottom-right) */}
      <div
        className="resize-handle absolute bottom-0 right-0 z-10 cursor-ns-resize opacity-30 hover:opacity-60 transition-opacity pointer-events-auto"
        onMouseDown={onResizeStart}
        title="Redimensionner"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M16 4L4 16M16 10L10 16M16 16L16 16" stroke="var(--text-faint)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
    </div>
  )
}
