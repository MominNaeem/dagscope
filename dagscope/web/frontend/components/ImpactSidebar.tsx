'use client';

import type { Direction, ImpactNode, ImpactResult } from '@/lib/types';

interface Props {
  nodeId: string | null;
  impact: ImpactResult | null;
  loading: boolean;
  direction: Direction;
  onDirectionChange: (d: Direction) => void;
}

function hopColor(hops: number): string {
  if (hops <= 1) return 'text-green border-green';
  if (hops <= 2) return 'text-green/60 border-green/40';
  if (hops <= 4) return 'text-amber/60 border-amber/30';
  return 'text-muted border-muted/30';
}

function NodeRow({ node }: { node: ImpactNode }) {
  return (
    <div className={`flex items-center justify-between px-3 py-2 rounded border-l-2 bg-surface/60 ${hopColor(node.hops)}`}>
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-xs text-muted shrink-0">
          {node.kind === 'task' ? '⬡' : '⬢'}
        </span>
        <span className="text-xs font-mono text-text truncate">{node.node_id}</span>
      </div>
      <span className="text-xs font-mono shrink-0 ml-2">{node.hops}h</span>
    </div>
  );
}

export default function ImpactSidebar({ nodeId, impact, loading, direction, onDirectionChange }: Props) {
  const byHop = impact?.nodes.reduce<Record<number, ImpactNode[]>>((acc, n) => {
    (acc[n.hops] ??= []).push(n);
    return acc;
  }, {}) ?? {};

  return (
    <div className="flex flex-col h-full text-sm">
      {/* Direction toggle */}
      <div className="flex gap-1 p-3 pb-2">
        {(['downstream', 'upstream'] as Direction[]).map((d) => (
          <button
            key={d}
            onClick={() => onDirectionChange(d)}
            className={`flex-1 py-1.5 rounded text-xs font-medium transition-colors ${
              direction === d
                ? 'bg-green/15 text-green border border-green/30'
                : 'bg-surface text-muted border border-border hover:text-text'
            }`}
          >
            {d === 'downstream' ? '↓ downstream' : '↑ upstream'}
          </button>
        ))}
      </div>

      {/* Selected node */}
      {nodeId && (
        <div className="px-3 pb-2">
          <div className="text-xs text-muted mb-1">selected</div>
          <div className="bg-purple/10 border border-purple/30 rounded px-2 py-1.5 text-xs font-mono text-purple truncate">
            {nodeId}
          </div>
        </div>
      )}

      {/* Results */}
      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {!nodeId && (
          <p className="text-xs text-muted mt-4 text-center">Click any node to inspect</p>
        )}

        {nodeId && loading && (
          <div className="flex items-center gap-2 mt-4 text-xs text-muted">
            <span className="animate-spin">⟳</span> Loading…
          </div>
        )}

        {impact && !loading && impact.nodes.length === 0 && (
          <p className="text-xs text-muted mt-4 text-center">No {direction} dependencies</p>
        )}

        {impact && !loading && impact.nodes.length > 0 && (
          <>
            <div className="text-xs text-muted mb-2">
              {impact.nodes.length} node{impact.nodes.length !== 1 ? 's' : ''} affected
            </div>
            <div className="flex flex-col gap-1">
              {Object.entries(byHop)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([hop, nodes]) => (
                  <div key={hop}>
                    <div className="text-xs text-muted/60 mb-1">hop {hop}</div>
                    {nodes.map((n) => <NodeRow key={n.node_id} node={n} />)}
                  </div>
                ))}
            </div>

            <a
              href={`/impact/${encodeURIComponent(nodeId ?? '')}`}
              target="_blank"
              rel="noreferrer"
              className="mt-3 flex items-center justify-center gap-1 text-xs text-muted hover:text-text border border-border rounded py-1.5 transition-colors"
            >
              ↗ shareable page
            </a>
          </>
        )}
      </div>
    </div>
  );
}
