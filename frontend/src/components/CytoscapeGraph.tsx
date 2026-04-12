import cytoscape, { type Core, type EventObject, type ElementDefinition } from 'cytoscape'
import { useEffect, useRef, useState, useCallback } from 'react'

/* ── Types ──────────────────────────────────────── */

interface CytoscapeGraphProps {
  dependencyGraph: Record<string, string[]>
  entryPoints: string[]
  coreModules: string[]
  orphanModules: string[]
  dependencyCycles: string[][]
  moduleDescriptions?: Record<string, string>
}

interface TooltipState {
  visible: boolean
  x: number
  y: number
  module: string
  role: string
  description?: string
}

/* ── Helpers ────────────────────────────────────── */

function getRole(
  id: string,
  entryPoints: string[],
  coreModules: string[],
  orphanModules: string[],
): string {
  if (entryPoints.includes(id)) return 'entry'
  if (coreModules.includes(id)) return 'core'
  if (orphanModules.includes(id)) return 'orphan'
  return 'default'
}

function getCycleEdgeIds(cycles: string[][]): Set<string> {
  const ids = new Set<string>()
  for (const cycle of cycles) {
    for (let i = 0; i < cycle.length; i++) {
      ids.add(`${cycle[i]}->${cycle[(i + 1) % cycle.length]}`)
    }
  }
  return ids
}

/** Topological sort: BFS from entry points, then remaining nodes. */
function topoSort(
  graph: Record<string, string[]>,
  entryPoints: string[],
): string[] {
  const inDegree = new Map<string, number>()
  const allNodes = new Set<string>()

  for (const [src, targets] of Object.entries(graph)) {
    allNodes.add(src)
    if (!inDegree.has(src)) inDegree.set(src, 0)
    for (const t of targets) {
      allNodes.add(t)
      inDegree.set(t, (inDegree.get(t) ?? 0) + 1)
    }
  }

  const queue: string[] = []
  // Start with entry points (in-degree 0 or known entries)
  for (const ep of entryPoints) {
    if (allNodes.has(ep) && (inDegree.get(ep) ?? 0) === 0) queue.push(ep)
  }
  // Then any node with in-degree 0
  for (const n of allNodes) {
    if (!queue.includes(n) && (inDegree.get(n) ?? 0) === 0) queue.push(n)
  }

  const sorted: string[] = []
  const visited = new Set<string>()

  while (queue.length > 0) {
    const node = queue.shift()!
    if (visited.has(node)) continue
    visited.add(node)
    sorted.push(node)

    for (const target of graph[node] ?? []) {
      const deg = (inDegree.get(target) ?? 1) - 1
      inDegree.set(target, deg)
      if (deg === 0 && !visited.has(target)) queue.push(target)
    }
  }

  // Add any remaining unvisited nodes (cycles / orphans)
  for (const n of allNodes) {
    if (!visited.has(n)) sorted.push(n)
  }

  return sorted
}

/** Assign depth (column) to each node based on longest path from entries. */
function computeDepths(
  graph: Record<string, string[]>,
  entryPoints: string[],
  order: string[],
): Map<string, number> {
  const depths = new Map<string, number>()
  const allNodes = new Set(order)

  // Build reverse adjacency (who depends on me)
  const dependents = new Map<string, string[]>()
  for (const [src, targets] of Object.entries(graph)) {
    for (const t of targets) {
      if (!dependents.has(t)) dependents.set(t, [])
      dependents.get(t)!.push(src)
    }
  }

  // BFS from entry points to assign depth
  const queue = entryPoints.filter(ep => allNodes.has(ep))
  for (const ep of queue) depths.set(ep, 0)

  while (queue.length > 0) {
    const node = queue.shift()!
    const depth = depths.get(node) ?? 0
    for (const target of graph[node] ?? []) {
      const newDepth = depth + 1
      if ((depths.get(target) ?? 0) < newDepth) {
        depths.set(target, newDepth)
        queue.push(target)
      }
    }
  }

  // Assign depth 0 to any node without a depth
  for (const n of allNodes) {
    if (!depths.has(n)) depths.set(n, 0)
  }

  return depths
}

function buildElements(
  graph: Record<string, string[]>,
  entryPoints: string[],
  coreModules: string[],
  orphanModules: string[],
  cycleEdgeIds: Set<string>,
): ElementDefinition[] {
  const elements: ElementDefinition[] = []
  const allNodes = new Set<string>()

  for (const [source, targets] of Object.entries(graph)) {
    allNodes.add(source)
    for (const t of targets) allNodes.add(t)
  }

  for (const node of allNodes) {
    elements.push({
      data: {
        id: node,
        label: node.split('/').pop() || node,
        role: getRole(node, entryPoints, coreModules, orphanModules),
      },
    })
  }

  const seenEdges = new Set<string>()
  for (const [source, targets] of Object.entries(graph)) {
    for (const target of targets) {
      const edgeId = `${source}->${target}`
      if (seenEdges.has(edgeId)) continue
      seenEdges.add(edgeId)
      elements.push({
        data: { id: edgeId, source, target },
        classes: cycleEdgeIds.has(edgeId) ? 'cycle' : '',
      })
    }
  }

  return elements
}

/** Position nodes in horizontal columns by dependency depth. */
function positionNodes(
  cy: Core,
  graph: Record<string, string[]>,
  entryPoints: string[],
  nodeW: number,
  nodeH: number,
  gapX: number,
  gapY: number,
) {
  const order = topoSort(graph, entryPoints)
  const depths = computeDepths(graph, entryPoints, order)

  // Group nodes by depth
  const columns = new Map<number, string[]>()
  for (const node of order) {
    const d = depths.get(node) ?? 0
    if (!columns.has(d)) columns.set(d, [])
    columns.get(d)!.push(node)
  }

  // Position each column
  for (const [depth, nodes] of columns) {
    const x = depth * (nodeW + gapX)
    for (let i = 0; i < nodes.length; i++) {
      const y = i * (nodeH + gapY)
      cy.getElementById(nodes[i]).position({ x, y })
    }
  }
}

/* ── Stylesheet ─────────────────────────────────── */

function getStylesheet(isDark: boolean) {
  const bg = isDark ? '#0a0a0a' : '#fafafa'
  const text = isDark ? '#a3a3a3' : '#737373'
  const textBright = isDark ? '#e5e5e5' : '#171717'
  const border = isDark ? '#262626' : '#e5e5eb'
  const borderBright = isDark ? '#404040' : '#d4d4d8'
  const edgeColor = isDark ? '#262626' : '#e5e5eb'
  const arrowColor = isDark ? '#404040' : '#a3a3a3'
  const hoverBorder = isDark ? '#525252' : '#a3a3a3'

  return [
    { selector: 'core', style: { 'background-color': bg } },

    {
      selector: 'node',
      style: {
        'background-color': bg,
        'border-color': border,
        'border-width': 1,
        color: text,
        'font-family': '"JetBrains Mono", ui-monospace, monospace',
        'font-size': '13px',
        label: 'data(label)',
        'text-valign': 'center',
        'text-halign': 'center',
        width: 140,
        height: 44,
        shape: 'round-rectangle' as const,
        'text-margin-x': 10,
        'text-margin-y': 0,
      },
    },

    {
      selector: 'node[role="entry"]',
      style: {
        'border-color': borderBright,
        'border-width': 1.5,
        color: textBright,
        'font-weight': 600,
      },
    },
    {
      selector: 'node[role="core"]',
      style: {
        'border-color': borderBright,
        'border-width': 1.5,
        color: textBright,
        'font-weight': 500,
      },
    },
    {
      selector: 'node[role="orphan"]',
      style: {
        'border-style': 'dashed' as const,
        opacity: 0.6,
      },
    },

    {
      selector: 'edge',
      style: {
        width: 1,
        'line-color': edgeColor,
        'target-arrow-color': arrowColor,
        'target-arrow-shape': 'triangle' as const,
        'arrow-scale': 0.5,
        'curve-style': 'bezier' as const,
        opacity: 0.6,
      },
    },
    {
      selector: 'edge.cycle',
      style: {
        width: 1,
        'line-style': 'dashed' as const,
        'line-color': isDark ? '#404040' : '#d4d4d8',
        'target-arrow-color': isDark ? '#525252' : '#a3a3a3',
        opacity: 0.5,
      },
    },
    {
      selector: '.hover',
      style: {
        'border-width': 1.5,
        'border-color': hoverBorder,
      },
    },
  ]
}

/* ── Component ──────────────────────────────────── */

const NODE_W = 140
const NODE_H = 44
const GAP_X = 30
const GAP_Y = 14

export function CytoscapeGraph({
  dependencyGraph,
  entryPoints,
  coreModules,
  orphanModules,
  dependencyCycles,
  moduleDescriptions,
}: CytoscapeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const [tooltip, setTooltip] = useState<TooltipState>({
    visible: false, x: 0, y: 0, module: '', role: '',
  })

  useEffect(() => {
    if (!containerRef.current || Object.keys(dependencyGraph).length === 0) return

    const cycleEdgeIds = getCycleEdgeIds(dependencyCycles)
    const elements = buildElements(dependencyGraph, entryPoints, coreModules, orphanModules, cycleEdgeIds)
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark'

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: getStylesheet(isDark) as any,
      layout: { name: 'preset' },
      wheelSensitivity: 0.2,
      minZoom: 0.3,
      maxZoom: 2,
      boxSelectionEnabled: false,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      autoungrabify: true,
      selectionType: 'single',
    })

    // Custom horizontal layout by dependency depth
    positionNodes(cy, dependencyGraph, entryPoints, NODE_W, NODE_H, GAP_X, GAP_Y)
    cy.fit(undefined, 30)

    const onNodeOver = (evt: EventObject) => {
      const node = evt.target
      const pos = node.renderedPosition()
      const rect = containerRef.current!.getBoundingClientRect()
      const id = node.id()
      const role = getRole(id, entryPoints, coreModules, orphanModules)
      const labels: Record<string, string> = {
        entry: 'Point d\'entrée', core: 'Module core', orphan: 'Orphelin', default: 'Module',
      }

      setTooltip({
        visible: true,
        x: pos.x + rect.left - containerRef.current!.offsetLeft,
        y: pos.y + rect.top - containerRef.current!.offsetTop,
        module: id,
        role: labels[role] || role,
        description: moduleDescriptions?.[id],
      })
    }

    const onNodeOut = () => setTooltip(prev => ({ ...prev, visible: false }))

    cy.on('mouseover', 'node', onNodeOver)
    cy.on('mouseout', 'node', onNodeOut)

    cyRef.current = cy
    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [dependencyGraph, entryPoints, coreModules, orphanModules, dependencyCycles, moduleDescriptions])

  // Theme reactivity
  useEffect(() => {
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.attributeName === 'data-theme' && cyRef.current) {
          const isDark = document.documentElement.getAttribute('data-theme') === 'dark'
          cyRef.current.style(getStylesheet(isDark) as any)
          cyRef.current.fit(undefined, 30)
        }
      }
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  const fitToView = useCallback(() => {
    cyRef.current?.fit(undefined, 30)
  }, [])

  return (
    <div className="relative group/diagram">
      <div
        ref={containerRef}
        className="rounded-lg border border-[var(--border)] overflow-hidden"
        style={{ height: 500, width: '100%' }}
      />

      {/* Tooltip */}
      {tooltip.visible && (
        <div
          className="pointer-events-none absolute z-50 px-3 py-2 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg shadow-xs max-w-[260px]"
          style={{ left: tooltip.x + 14, top: tooltip.y - 10 }}
        >
          <div className="font-mono text-[11px] font-medium text-[var(--text)] leading-snug">
            {tooltip.module}
          </div>
          {tooltip.description && (
            <div className="text-[11px] text-[var(--text-muted)] mt-1 leading-snug">
              {tooltip.description}
            </div>
          )}
          <div className="text-[9px] mt-1.5 text-[var(--text-faint)] uppercase tracking-widest font-medium">
            {tooltip.role}
          </div>
        </div>
      )}

      {/* Fit button */}
      <button
        onClick={fitToView}
        className="absolute top-3 right-3 w-7 h-7 rounded-md bg-[var(--bg-card)]/90 backdrop-blur-sm border border-[var(--border)] flex items-center justify-center text-[var(--text-faint)] hover:text-[var(--text-muted)] opacity-0 group-hover/diagram:opacity-100 transition-opacity z-10"
        title="Ajuster la vue"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M1 5h1M10 5h1M6 1v1M6 10v1M2.5 2.5l.7.7M8.8 8.8l.7.7M2.5 9.5l.7-.7M8.8 3.2l.7-.7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        </svg>
      </button>
    </div>
  )
}
