import { api } from './client'
import { API_ENDPOINTS } from '../constants/apiEndpoints'
import type { Map3DConfig, Entity3D } from '../types/map3d'

export async function get3DConfig(): Promise<Map3DConfig> {
  return api.get<Map3DConfig>(API_ENDPOINTS.map3d.config)
}

export async function get3DEntities(): Promise<{ entities: Entity3D[]; total: number }> {
  return api.get(API_ENDPOINTS.map3d.entities)
}

export async function geocode(address: string): Promise<unknown> {
  return api.get(API_ENDPOINTS.map3d.geocoder, { address })
}

export async function placeSearch(keyword: string, boundary?: string): Promise<unknown> {
  return api.get(API_ENDPOINTS.map3d.placeSearch, { keyword, boundary })
}

export async function getDirection(
  fromLat: number, fromLng: number,
  toLat: number, toLng: number,
): Promise<unknown> {
  return api.get(API_ENDPOINTS.map3d.direction, {
    from_lat: fromLat, from_lng: fromLng,
    to_lat: toLat, to_lng: toLng,
  })
}
