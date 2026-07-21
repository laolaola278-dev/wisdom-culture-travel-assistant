import { api } from './client'
import { API_ENDPOINTS } from '../constants/apiEndpoints'
import type { CategoryInfo, EntityListItem, NearbyPlace, RoutePlan } from '../types/explore'

export async function getCategories(): Promise<{ categories: CategoryInfo[] }> {
  return api.get(API_ENDPOINTS.explore.categories)
}

export async function getEntities(params: {
  type?: string
  limit?: number
}): Promise<{ type: string; count: number; entities: EntityListItem[] }> {
  return api.get(API_ENDPOINTS.graph.entities, params)
}

export async function getNearby(name: string): Promise<{ entity: string; nearby: NearbyPlace[] }> {
  return api.get(API_ENDPOINTS.explore.entityNearby(name))
}

export async function planRoute(start: string, end?: string, preferences?: Record<string, unknown>): Promise<RoutePlan> {
  return api.post<RoutePlan>(API_ENDPOINTS.explore.routePlan, { start, end, preferences })
}

export async function getCoordinates(params?: {
  entity?: string
  type?: string
  limit?: number
}): Promise<{ count: number; points: Array<{ name: string; lat: number; lng: number; type: string; display_name?: string; location?: string }> }> {
  return api.get(API_ENDPOINTS.explore.coordinates, params)
}

export async function aiSearch(query: string, searchType = 'general'): Promise<{ answer?: string; result?: string }> {
  return api.post(API_ENDPOINTS.explore.aiSearch, { query, search_type: searchType })
}

export async function getEntityEnhanced(name: string): Promise<Record<string, unknown>> {
  return api.get(API_ENDPOINTS.explore.entityEnhanced(name))
}

export async function getEntityContext(name: string): Promise<Record<string, unknown>> {
  return api.get(API_ENDPOINTS.explore.entityContext(name))
}
