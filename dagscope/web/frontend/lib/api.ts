import type { AISummary, Direction, GraphData, GraphSummary, ImpactResult } from './types';

// Server-side fetches go directly to FastAPI; client-side go through Next.js rewrite proxy
const API_BASE =
  typeof window === 'undefined' ? 'http://127.0.0.1:8000' : '';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  graph: (): Promise<GraphData> =>
    get('/api/graph'),

  impact: (nodeId: string, direction: Direction = 'downstream'): Promise<ImpactResult> =>
    get(`/api/impact/${encodeURIComponent(nodeId)}?direction=${direction}`),

  aiSummary: (nodeId: string, direction: Direction = 'downstream'): Promise<AISummary> =>
    get(`/api/ai-summary/${encodeURIComponent(nodeId)}?direction=${direction}`),

  cycles: (): Promise<{ cycles: string[][] }> =>
    get('/api/cycles'),

  summary: (): Promise<GraphSummary> =>
    get('/api/summary'),
};
