import { api } from './client'
import { API_ENDPOINTS } from '../constants/apiEndpoints'
import type { Overview, LocationFrequency } from '../types/stats'

export async function getOverview(): Promise<Overview> {
  return api.get<Overview>(API_ENDPOINTS.stats.overview)
}

export async function getLocationFrequency(topN = 30): Promise<LocationFrequency> {
  return api.get<LocationFrequency>(API_ENDPOINTS.stats.locationFrequency, { top_n: topN })
}
