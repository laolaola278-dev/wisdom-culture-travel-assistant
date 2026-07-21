import { api } from './client'
import { API_ENDPOINTS } from '../constants/apiEndpoints'
import type { Favorite } from '../types/common'

export async function getFavorites(): Promise<{ favorites: Favorite[] }> {
  return api.get(API_ENDPOINTS.favorites.list)
}

export async function addFavorite(item: {
  type: string
  id: string
  name?: string
}): Promise<{ message: string }> {
  return api.post(API_ENDPOINTS.favorites.add, item)
}

export async function removeFavorite(item: { type: string; id: string }): Promise<void> {
  return api.delete(API_ENDPOINTS.favorites.remove, item)
}
