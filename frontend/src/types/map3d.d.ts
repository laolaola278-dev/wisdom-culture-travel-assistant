/** 3D 地图类型定义 */

export interface Map3DConfig {
  tencent_map_key: string
  enable_3d: boolean
  center: [number, number]  // [lng, lat]
  zoom: number
  building_lod_max_distance: number
  traffic_update_interval: number
  crowd_update_interval: number
}

export interface Entity3D {
  id: number
  name: string
  display_name: string
  type: string
  lat: number
  lng: number
  address: string
  location: string
}

export interface POIMarkerData {
  id: number
  position: [number, number, number]  // Three.js 世界坐标
  entity: Entity3D
  color: string
  icon: string
}

export interface LODLevel {
  distance: number
  buildingPrecision: 'fine' | 'extruded' | 'box' | 'none'
  textureResolution: number
  labelVisible: boolean
}

export type CameraPreset = 'top-down' | 'street-view' | 'perspective' | 'free'

export interface RealtimeTrafficData {
  location: [number, number]
  speed: number
  status: 'smooth' | 'slow' | 'congested' | 'severe'
  timestamp: number
}

export interface RealtimeCrowdData {
  location: [number, number]
  count: number
  level: 'low' | 'medium' | 'high'
  timestamp: number
}

export interface LayerState {
  buildings: boolean
  roads: boolean
  traffic: boolean
  poi: boolean
  crowd: boolean
  labels: boolean
}

export interface Map3DState {
  ready: boolean
  loading: boolean
  config: Map3DConfig | null
  entities: Entity3D[]
  layers: LayerState
  selectedEntity: Entity3D | null
  cameraPreset: CameraPreset
  realtimeTraffic: RealtimeTrafficData[]
  realtimeCrowd: RealtimeCrowdData[]
}