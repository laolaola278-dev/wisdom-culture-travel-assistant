import { api } from './client'
import { API_ENDPOINTS } from '../constants/apiEndpoints'
import type { GraphData, EntityDetail, SearchResult } from '../types/graph'

export async function getGraphVisualization(limit = 150, type?: string): Promise<GraphData> {
  return api.get<GraphData>(API_ENDPOINTS.graph.visualization, { limit, type })
}

export async function getEntityDetail(name: string): Promise<EntityDetail> {
  return api.get<EntityDetail>(API_ENDPOINTS.graph.entity(name))
}

export async function searchEntities(query: string, topK = 10): Promise<{ query: string; results: SearchResult[] }> {
  return api.get(API_ENDPOINTS.graph.search, { q: query, top_k: topK })
}

export async function getGraphStats(): Promise<Record<string, unknown>> {
  return api.get(API_ENDPOINTS.graph.stats)
}
