'use client';

import { useEffect, useRef } from 'react';
import type { GraphData } from '@/lib/types';

// vis-network is DOM-only — this component must never render on the server.
// The parent page imports it via next/dynamic with { ssr: false }.
import type { Network as VisNetwork, Options } from 'vis-network';

interface Props {
  data: GraphData;
  selectedNode: string | null;
  blastRadius: Set<string>;
  onNodeSelect: (nodeId: string) => void;
}

const NODE_COLORS: Record<string, { bg: string; border: string }> = {
  task:  { bg: '#1a2a3a', border: '#2a4a6a' },
  table: { bg: '#003d2e', border: '#22d3a0' },
};

const VIS_OPTIONS: Options = {
  nodes: {
    shape: 'ellipse',
    font: { size: 11, face: 'ui-monospace, monospace', color: '#e8edf7' },
    borderWidth: 1.5,
    borderWidthSelected: 2.5,
    shadow: false,
    widthConstraint: { maximum: 150 },
  },
  edges: {
    arrows: { to: { enabled: true, scaleFactor: 0.5 } },
    color: { color: '#2a3d5a', highlight: '#f5a623', hover: '#3a4d6a' },
    width: 1.2,
    smooth: { enabled: true, type: 'cubicBezier', roundness: 0.5 },
  },
  physics: { enabled: false },
  layout: {
    hierarchical: {
      enabled: true,
      direction: 'LR',
      sortMethod: 'directed',
      levelSeparation: 140,
      nodeSpacing: 60,
      treeSpacing: 80,
      blockShifting: true,
      edgeMinimization: true,
      parentCentralization: true,
    },
  },
  interaction: { hover: true, tooltipDelay: 150, zoomView: true, dragView: true },
};

export default function GraphCanvas({ data, selectedNode, blastRadius, onNodeSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef   = useRef<VisNetwork | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nodesDataRef = useRef<any>(null);

  // Build and mount the network once
  useEffect(() => {
    if (!containerRef.current) return;

    // Dynamic import keeps vis-network out of the SSR bundle
    Promise.all([import('vis-network'), import('vis-data')]).then(([visNet, visData]) => {
      const { Network } = visNet;
      const { DataSet } = visData;

      const nodes = new DataSet(
        data.nodes.map((n) => ({
          id: n.id,
          // Short label for the node — full ID shown in tooltip on hover
          label: n.id.split('.').pop() ?? n.id,
          color: {
            background: (NODE_COLORS[n.kind] ?? NODE_COLORS.table).bg,
            border:     (NODE_COLORS[n.kind] ?? NODE_COLORS.table).border,
          },
          font: { color: '#e8edf7' },
          title: [
            n.id,
            n.kind,
            n.confidence === 'low' ? '⚠ low confidence' : null,
          ].filter(Boolean).join('\n'),
        }))
      );

      const edges = new DataSet(
        data.edges.map((e, i) => ({
          id: i,
          from: e.from,
          to: e.to,
          dashes: e.confidence === 'low',
          color: e.kind === 'task_dep' ? { color: '#1a2a3a' } : undefined,
        }))
      );

      nodesDataRef.current = nodes;

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const network = new (Network as any)(containerRef.current!, { nodes, edges }, VIS_OPTIONS) as VisNetwork;

      networkRef.current = network;

      // Hierarchical layout positions nodes synchronously but the viewport needs
      // a tick to reflect the final positions before fit() works correctly.
      setTimeout(() => {
        network.fit({ animation: false });
        const scale = network.getScale();
        // If the graph is tiny (many levels), zoom in to a readable minimum
        if (scale < 0.7) network.moveTo({ scale: 0.7 });
      }, 150);

      network.on('click', (params) => {
        if (params.nodes.length > 0) onNodeSelect(String(params.nodes[0]));
      });
    });

    return () => {
      networkRef.current?.destroy();
      networkRef.current = null;
      nodesDataRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  // Re-color nodes when selection/blast radius changes
  useEffect(() => {
    if (!nodesDataRef.current) return;

    const updates = data.nodes.map((n) => {
      const isSelected = n.id === selectedNode;
      const inBlast    = blastRadius.has(n.id);

      let bg     = (NODE_COLORS[n.kind] ?? NODE_COLORS.table).bg;
      let border = (NODE_COLORS[n.kind] ?? NODE_COLORS.table).border;

      if (isSelected)     { bg = '#3d0a24'; border = '#ff4060'; }
      else if (inBlast)   { bg = '#2d1f00'; border = '#f5a623'; }

      return { id: n.id, color: { background: bg, border } };
    });

    nodesDataRef.current.update(updates);
  }, [selectedNode, blastRadius, data.nodes]);

  return <div ref={containerRef} className="graph-container" />;
}
