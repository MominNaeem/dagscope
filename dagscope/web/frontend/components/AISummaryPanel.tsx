'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { AISummary, Direction } from '@/lib/types';

interface Props {
  nodeId: string | null;
  direction: Direction;
}

const SEVERITY_STYLES: Record<string, string> = {
  low:      'bg-green/10  text-green border-green/30',
  medium:   'bg-amber/10  text-amber  border-amber/30',
  high:     'bg-red/10    text-red    border-red/30',
  critical: 'bg-red/20    text-red    border-red/50  font-semibold',
};

export default function AISummaryPanel({ nodeId, direction }: Props) {
  const [summary, setSummary]   = useState<AISummary | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error,   setError]     = useState<string | null>(null);
  // Cache: avoid re-fetching the same node+direction
  const [cacheKey, setCacheKey] = useState('');

  useEffect(() => {
    if (!nodeId) return;
    const key = `${nodeId}:${direction}`;
    if (key === cacheKey) return;

    setLoading(true);
    setError(null);
    setSummary(null);

    api.aiSummary(nodeId, direction)
      .then((s) => {
        // FastAPI returns {error: string} when API key is missing or summarize() returns None
        if ('error' in s) {
          setError((s as unknown as { error: string }).error);
        } else {
          setSummary(s);
          setCacheKey(key);
        }
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [nodeId, direction, cacheKey]);

  if (!nodeId) {
    return <p className="text-xs text-muted mt-4 text-center px-3">Click any node to get an AI summary</p>;
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-3 mt-8 text-muted">
        <span className="text-2xl animate-spin">⟳</span>
        <p className="text-xs">Asking Claude…</p>
      </div>
    );
  }

  if (error) {
    return <p className="text-xs text-muted/60 mt-4 px-3">{error}</p>;
  }

  if (!summary) return null;

  return (
    <div className="flex flex-col gap-3 p-3 text-xs overflow-y-auto">
      {/* Severity badge */}
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded border w-fit ${SEVERITY_STYLES[summary.severity] ?? ''}`}>
        <span>●</span>
        <span>{summary.severity}</span>
      </div>

      {/* Summary prose */}
      <p className="text-text/80 leading-relaxed">{summary.summary}</p>

      {/* Recommended checks */}
      {(summary.recommended_checks?.length ?? 0) > 0 && (
        <div>
          <div className="text-muted mb-1.5 font-medium">Recommended checks</div>
          <ul className="flex flex-col gap-1">
            {(summary.recommended_checks ?? []).map((check, i) => (
              <li key={i} className="flex gap-2 text-text/70">
                <span className="text-green shrink-0">•</span>
                {check}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Uncertainty note */}
      {summary.uncertainty && (
        <p className="text-muted/60 italic border-t border-border pt-2">{summary.uncertainty}</p>
      )}
    </div>
  );
}
