export interface CategoryInfo {
  key: string
  name: string
  count: number
  icon?: string
}

export interface EntityListItem {
  id: number
  name: string
  display_name: string
  type: string
  address: string
  location: string
  lat?: number
  lng?: number
  description?: string
}

export interface NearbyPlace {
  name: string
  type: string
  address: string
  distance: number
  lat: number
  lng: number
}

export interface RoutePlan {
  distance: number
  duration: number
  steps: { instruction: string; distance: number }[]
  polyline: [number, number][]
}
