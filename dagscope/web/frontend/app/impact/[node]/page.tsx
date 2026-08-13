// Server Component — data is fetched on the server before the page is sent.
// This means /impact/public.positions_daily returns a fully-rendered HTML page
// that you can share as a link — no client-side loading state needed.

import type { Metadata } from 'next';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { ImpactNode, Severity } from '@/lib/types';

interface PageProps {
  params: Promise<{ node: string }>;
  searchParams: Promise<{ direction?: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { node } = await params;
  const nodeId = decodeURIComponent(node);
  return {
    title: `Impact: ${nodeId} — dagscope`,
    description: `Blast radius analysis for ${nodeId}`,
  };
}

function severityStyle(severity: Severity): string {
  return {
    low:      'bg-green/10  text-green border-green/40',
    medium:   'bg-amber/10  text-amber  border-amber/40',
    high:     'bg-red/10    text-red    border-red/40',
    critical: 'bg-red/20    text-red    border-red/60',
  }[severity] ?? '';
}

function hopBadge(hops: number): string {
  if (hops <= 1) return 'text-green  bg-green/10';
  if (hops <= 2) return 'text-green/60 bg-green/5';
  if (hops <= 4) return 'text-amber/60 bg-amber/5';
  return 'text-muted bg-muted/10';
}

function NodeRow({ node }: { node: ImpactNode }) {
  return (
    <tr className="border-b border-border last:border-0">
      <td className="py-2 px-3 font-mono text-xs text-text">{node.node_id}</td>
      <td className="py-2 px-3 text-xs text-muted">{node.kind}</td>
      <td className="py-2 px-3 text-right">
        <span className={`inline-block text-xs font-mono px-1.5 py-0.5 rounded ${hopBadge(node.hops)}`}>
          {node.hops}
        </span>
      </td>
    </tr>
  );
}

export default async function ImpactPage({ params, searchParams }: PageProps) {
  const { node } = await params;
  const { direction: dirParam } = await searchParams;
  const nodeId    = decodeURIComponent(node);
  const direction = dirParam === 'upstream' ? 'upstream' : 'downstream';

  let impact: import('@/lib/types').ImpactResult | null = null;
  let aiSummary: import('@/lib/types').AISummary | null = null;
  let fetchError: string | null = null;

  try {
    const [ir, ar] = await Promise.allSettled([
      api.impact(nodeId, direction),
      api.aiSummary(nodeId, direction),
    ]);
    if (ir.status === 'fulfilled') impact = ir.value;
    if (ar.status === 'fulfilled') aiSummary = ar.value;
  } catch {
    fetchError = 'Could not reach the dagscope API. Make sure `dagscope serve` is running.';
  }

  return (
    <div className="min-h-screen bg-canvas text-text">
      <div className="max-w-3xl mx-auto px-6 py-10">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-muted mb-8">
          <Link href="/" className="hover:text-text transition-colors">◈ dagscope</Link>
          <span>/</span>
          <span>impact</span>
          <span>/</span>
          <span className="text-purple font-mono">{nodeId}</span>
        </div>

        {/* Title */}
        <h1 className="text-xl font-mono font-semibold mb-1">{nodeId}</h1>
        <p className="text-sm text-muted mb-6">
          {direction === 'downstream' ? 'Downstream blast radius' : 'Upstream provenance'} ·{' '}
          <a
            href={`/impact/${node}?direction=${direction === 'downstream' ? 'upstream' : 'downstream'}`}
            className="text-green hover:underline"
          >
            switch to {direction === 'downstream' ? 'upstream' : 'downstream'}
          </a>
        </p>

        {fetchError && (
          <p className="text-red text-sm bg-red/10 border border-red/30 rounded px-4 py-3">{fetchError}</p>
        )}

        {/* AI Summary */}
        {aiSummary && (
          <div className="mb-6 border border-border rounded-lg p-4 bg-surface">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-purple text-xs font-medium">AI Summary</span>
              <span className={`text-xs px-2 py-0.5 rounded border ${severityStyle(aiSummary.severity)}`}>
                {aiSummary.severity}
              </span>
            </div>
            <p className="text-sm text-text/80 leading-relaxed mb-3">{aiSummary.summary}</p>
            {aiSummary.recommended_checks.length > 0 && (
              <ul className="flex flex-col gap-1">
                {aiSummary.recommended_checks.map((c, i) => (
                  <li key={i} className="text-xs text-text/70 flex gap-2">
                    <span className="text-green">•</span>{c}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Impact table */}
        {impact && (
          <>
            <div className="text-xs text-muted mb-2">{impact.nodes.length} nodes affected</div>
            <div className="border border-border rounded-lg overflow-hidden bg-surface">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border text-xs text-muted">
                    <th className="py-2 px-3 text-left font-medium">Node</th>
                    <th className="py-2 px-3 text-left font-medium">Kind</th>
                    <th className="py-2 px-3 text-right font-medium">Hops</th>
                  </tr>
                </thead>
                <tbody>
                  {impact.nodes.map((n) => <NodeRow key={n.node_id} node={n} />)}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Back link */}
        <div className="mt-8">
          <Link
            href="/"
            className="text-xs text-muted hover:text-text border border-border rounded px-3 py-1.5 inline-flex items-center gap-1.5 transition-colors"
          >
            ← open in graph explorer
          </Link>
        </div>
      </div>
    </div>
  );
}
