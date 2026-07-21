export interface GraphNode {
  id: string
  label: string
  category: string
  symbolSize?: number
  itemStyle?: { color: string }
}

export interface GraphEdge {
  source: string
  target: string
  label?: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface EntityDetail {
  name: string
  type: string
  display_name: string
  address: string
  location: string
  description: string
  related: { name: string; type: string; relation: string }[]
}

export interface SearchResult {
  name: string
  type: string
  score: number
}
