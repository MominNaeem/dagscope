// Mirrors dagscope's Pydantic models exactly — single source of truth is the Python side

export type NodeKind = 'task' | 'table';
export type Direction = 'downstream' | 'upstream';
export type Confidence = 'high' | 'low';
export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type EdgeKind = 'task_dep' | 'reads' | 'writes';

export interface GraphNode {
  id: string;
  kind: NodeKind;
  dag_id?: string;
  task_id?: string;
  operator_class?: string;
  confidence?: Confidence;
}

export interface GraphEdge {
  from: string;
  to: string;
  kind: EdgeKind;
  confidence?: Confidence;
  statement_type?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ImpactNode {
  node_id: string;
  kind: NodeKind;
  hops: number;
}

export interface ImpactResult {
  query_node: string;
  direction: Direction;
  nodes: ImpactNode[];
}

export interface AISummary {
  severity: Severity;
  summary: string;
  affected_assets: string[];
  recommended_checks: string[];
  uncertainty?: string;
}

export interface GraphSummary {
  task_count: number;
  table_count: number;
  edge_count: number;
  low_confidence_edge_count: number;
  dag_count: number;
}
