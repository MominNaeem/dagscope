'use client';

import dynamic from 'next/dynamic';
import { useEffect, useState, useCallback } from 'react';
import ImpactSidebar from '@/components/ImpactSidebar';
import AISummaryPanel from '@/components/AISummaryPanel';
import { api } from '@/lib/api';
import type { Direction, GraphData, GraphSummary, ImpactResult } from '@/lib/types';

// vis-network accesses the DOM — never SSR
const GraphCanvas = dynamic(() => import('@/components/GraphCanvas'), { ssr: false });

type Tab = 'blast' | 'ai';

export default function Home() {
  const [graphData,   setGraphData]   = useState<GraphData | null>(null);
  const [summary,     setSummary]     = useState<GraphSummary | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [blastRadius, setBlastRadius] = useState<Set<string>>(new Set());
  const [impact,      setImpact]      = useState<ImpactResult | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [direction,   setDirection]   = useState<Direction>('downstream');
  const [tab,         setTab]         = useState<Tab>('blast');
  const [error,       setError]       = useState<string | null>(null);

  // Load graph on mount
  useEffect(() => {
    Promise.all([api.graph(), api.summary()])
      .then(([g, s]) => { setGraphData(g); setSummary(s); })
      .catch(() => setError('Could not connect to dagscope API — is `dagscope serve` running?'));
  }, []);

  // Fetch impact when node or direction changes
  useEffect(() => {
    if (!selectedNode) return;
    setImpactLoading(true);
    api.impact(selectedNode, direction)
      .then((r) => {
        setImpact(r);
        setBlastRadius(new Set(r.nodes.map((n) => n.node_id)));
      })
      .catch(() => { setImpact(null); setBlastRadius(new Set()); })
      .finally(() => setImpactLoading(false));
  }, [selectedNode, direction]);

  const handleNodeSelect = useCallback((nodeId: string) => {
    setSelectedNode(nodeId);
    setImpact(null);
    setBlastRadius(new Set());
    setTab('blast');
  }, []);

  const handleDirectionChange = useCallback((d: Direction) => {
    setDirection(d);
    setImpact(null);
    setBlastRadius(new Set());
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-canvas">
      {/* Sidebar */}
      <aside className="w-72 shrink-0 flex flex-col border-r border-border bg-surface">
        {/* Header */}
        <div className="px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <span className="text-green font-mono font-bold text-base">◈ dagscope</span>
          </div>
          {summary && (
            <div className="flex gap-3 mt-1.5 text-xs text-muted font-mono">
              <span>{summary.dag_count} DAGs</span>
              <span>{summary.task_count} tasks</span>
              <span>{summary.table_count} tables</span>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border">
          {(['blast', 'ai'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2 text-xs font-medium transition-colors ${
                tab === t
                  ? 'text-text border-b-2 border-green'
                  : 'text-muted hover:text-text'
              }`}
            >
              {t === 'blast' ? 'Blast Radius' : 'AI Analysis'}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-hidden">
          {tab === 'blast' ? (
            <ImpactSidebar
              nodeId={selectedNode}
              impact={impact}
              loading={impactLoading}
              direction={direction}
              onDirectionChange={handleDirectionChange}
            />
          ) : (
            <AISummaryPanel nodeId={selectedNode} direction={direction} />
          )}
        </div>
      </aside>

      {/* Main graph area */}
      <main className="flex-1 relative overflow-hidden">
        {error && (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-sm text-muted max-w-sm text-center">{error}</p>
          </div>
        )}

        {!error && !graphData && (
          <div className="absolute inset-0 flex items-center justify-center gap-2 text-muted text-sm">
            <span className="animate-spin">⟳</span> Building graph…
          </div>
        )}

        {graphData && (
          <GraphCanvas
            data={graphData}
            selectedNode={selectedNode}
            blastRadius={blastRadius}
            onNodeSelect={handleNodeSelect}
          />
        )}

        {/* Corner hint */}
        {!selectedNode && graphData && (
          <div className="absolute bottom-4 right-4 text-xs text-muted/50 pointer-events-none">
            click a node to inspect
          </div>
        )}
      </main>
    </div>
  );
}
