import { useState, useCallback, useMemo } from 'react'

interface Props {
  dependencyGraph: Record<string, string[]>
  entryPoints: string[]
  coreModules: string[]
  orphanModules: string[]
  moduleDescriptions?: Record<string, string>
}

interface TreeNode {
  id: string
  label: string
  fullPath: string
  children: TreeNode[]
  type: 'entry' | 'core' | 'orphan' | 'default'
  description?: string
  depth: number
}

function getNodeType(path: string, entryPoints: string[], coreModules: string[], orphanModules: string[]): TreeNode['type'] {
  if (entryPoints.includes(path)) return 'entry'
  if (coreModules.includes(path)) return 'core'
  if (orphanModules.includes(path)) return 'orphan'
  return 'default'
}

function buildTree(graph: Props): TreeNode[] {
  const { dependencyGraph, entryPoints, coreModules, orphanModules, moduleDescriptions } = graph
  const visited = new Set<string>()
  const allTargets = new Set<string>()
  if (!dependencyGraph) return []
  for (const deps of Object.values(dependencyGraph)) {
    for (const d of deps) allTargets.add(d)
  }

  const roots = [...entryPoints]
  if (roots.length === 0) {
    for (const node of Object.keys(dependencyGraph)) {
      if (!allTargets.has(node)) {
        roots.push(node)
      }
    }
  }
  if (roots.length === 0) {
    roots.push(...Object.keys(dependencyGraph).slice(0, 1))
  }

  function buildNode(path: string, depth: number): TreeNode {
    if (visited.has(path)) {
      return {
        id: path,
        label: path.split('/').pop() || path,
        fullPath: path,
        children: [],
        type: getNodeType(path, entryPoints, coreModules, orphanModules),
        description: moduleDescriptions?.[path],
        depth,
      }
    }
    visited.add(path)

    const children = (dependencyGraph[path] || [])
      .filter(d => dependencyGraph.hasOwnProperty(d))
      .map(d => buildNode(d, depth + 1))

    return {
      id: path,
      label: path.split('/').pop() || path,
      fullPath: path,
      children,
      type: getNodeType(path, entryPoints, coreModules, orphanModules),
      description: moduleDescriptions?.[path],
      depth,
    }
  }

  return roots.map(r => buildNode(r, 0))
}

function NodeBadge({ type }: { type: TreeNode['type'] }) {
  const styles: Record<string, string> = {
    entry: 'bg-blue-50 text-blue-700 border-blue-200',
    core: 'bg-[var(--bg)] text-[var(--text)] border-[var(--border-strong)]',
    orphan: 'bg-orange-50 text-orange-600 border-orange-200',
    default: 'bg-[var(--bg-card)] text-[var(--text-muted)] border-[var(--border)]',
  }
  const labels: Record<string, string> = {
    entry: 'entry',
    core: 'core',
    orphan: 'isolé',
    default: '',
  }
  if (type === 'default') return null
  return (
    <span className={`text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-[3px] border leading-none ${styles[type]}`}>
      {labels[type]}
    </span>
  )
}

function TreeNodeComponent({
  node,
  defaultExpanded,
}: {
  node: TreeNode
  defaultExpanded: boolean
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const hasChildren = node.children.length > 0

  const toggle = useCallback(() => {
    if (hasChildren) setExpanded(p => !p)
  }, [hasChildren])

  const nodeStyles: Record<string, string> = {
    entry: 'bg-blue-50 border-blue-200 hover:bg-blue-100',
    core: 'bg-[var(--bg)] border-[var(--border-strong)] hover:bg-[var(--bg-subtle)]',
    orphan: 'bg-orange-50/50 border-orange-100 hover:bg-orange-50',
    default: 'bg-[var(--bg-card)] border-[var(--border)] hover:bg-[var(--bg)]',
  }

  const dotStyles: Record<string, string> = {
    entry: 'bg-blue-500',
    core: 'bg-[var(--text)]',
    orphan: 'bg-orange-400',
    default: 'bg-[var(--border-strong)]',
  }

  return (
    <div className="select-none">
      <div
        className={`group flex items-center gap-2.5 py-1.5 px-2.5 rounded-md border cursor-pointer transition-all duration-150 ${nodeStyles[node.type]}`}
        onClick={toggle}
        title={node.description || node.fullPath}
      >
        {/* Expand arrow */}
        <span className={`w-3.5 h-3.5 flex items-center justify-center text-[var(--text-faint)] transition-transform duration-200 ${expanded ? 'rotate-90' : ''}`}>
          {hasChildren ? (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M3.5 2L6.5 5L3.5 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          ) : (
            <span className="block w-1.5 h-1.5 rounded-full" />
          )}
        </span>

        {/* Dot */}
        <span className={`w-2 h-2 rounded-full shrink-0 ${dotStyles[node.type]}`} />

        {/* Label */}
        <span className="text-[13px] font-mono font-medium text-[var(--text)] truncate">
          {node.label}
        </span>

        {/* Path hint */}
        {node.fullPath !== node.label && (
          <span className="text-[11px] text-[var(--text-faint)] font-mono truncate opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            {node.fullPath}
          </span>
        )}

        {/* Badge */}
        <span className="ml-auto shrink-0">
          <NodeBadge type={node.type} />
        </span>
      </div>

      {/* Children */}
      {hasChildren && expanded && (
        <div className="ml-5 pl-4 border-l border-[var(--border)] mt-0.5 space-y-0.5">
          {node.children.map(child => (
            <TreeNodeComponent
              key={child.id}
              node={child}
              defaultExpanded={child.depth < 2}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function DependencyTree(props: Props) {
  const [zoom, setZoom] = useState(100)
  const [filter, setFilter] = useState<string>('all')

  const tree = useMemo(() => buildTree(props), [props])

  const filteredTree = useMemo(() => {
    if (filter === 'all') return tree
    return tree.filter(n => n.type === filter || n.children.some(c => c.type === filter))
  }, [tree, filter])

  const stats = useMemo(() => ({
    entry: props.entryPoints.length,
    core: props.coreModules.length,
    orphan: props.orphanModules.length,
    total: Object.keys(props.dependencyGraph ?? {}).length,
  }), [props])

  if (tree.length === 0) {
    return (
      <div className="flex items-center justify-center h-[400px] text-[var(--text-faint)] text-[13px]">
        Aucune dépendance détectée
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          {(['all', 'entry', 'core', 'orphan'] as const).map(f => {
            const labels: Record<string, string> = { all: 'Tous', entry: 'Entry', core: 'Core', orphan: 'Isolés' }
            const counts: Record<string, number> = { all: stats.total, entry: stats.entry, core: stats.core, orphan: stats.orphan }
            return (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`text-[11px] font-medium px-2 py-1 rounded-md border transition-all duration-150 ${
                  filter === f
                    ? 'bg-[var(--text)] text-[var(--accent-text)] border-[var(--text)]'
                    : 'bg-[var(--bg-card)] text-[var(--text-faint)] border-[var(--border)] hover:bg-[var(--bg)] hover:border-[var(--border-strong)]'
                }`}
              >
                {labels[f]} <span className="opacity-60">{counts[f]}</span>
              </button>
            )
          })}
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setZoom(z => Math.max(60, z - 10))}
            className="w-6 h-6 flex items-center justify-center rounded border border-[var(--border)] text-[var(--text-muted)] hover:bg-[var(--bg)] text-[13px] font-mono transition-colors"
          >
            −
          </button>
          <span className="text-[11px] text-[var(--text-faint)] font-mono w-8 text-center">{zoom}%</span>
          <button
            onClick={() => setZoom(z => Math.min(140, z + 10))}
            className="w-6 h-6 flex items-center justify-center rounded border border-[var(--border)] text-[var(--text-muted)] hover:bg-[var(--bg)] text-[13px] font-mono transition-colors"
          >
            +
          </button>
        </div>
      </div>

      {/* Tree */}
      <div
        className="bg-[var(--bg)] border border-[var(--border)] rounded-lg p-4 overflow-auto"
        style={{ maxHeight: '600px', fontSize: `${zoom}%` }}
      >
        <div className="space-y-0.5">
          {filteredTree.map(node => (
            <TreeNodeComponent key={node.id} node={node} defaultExpanded />
          ))}
        </div>

        {/* Legend */}
        <div className="mt-6 pt-4 border-t border-[var(--border)] flex flex-wrap gap-4 text-[11px] text-[var(--text-faint)]">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-blue-500" /> Point d'entrée
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[var(--text)]" /> Module core
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-orange-400" /> Module isolé
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[var(--border-strong)]" /> Autre
          </span>
        </div>
      </div>
    </div>
  )
}
