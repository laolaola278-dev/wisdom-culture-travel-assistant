import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as map3dApi from '../api/map3d'
import type { Map3DConfig, Entity3D, LayerState, CameraPreset } from '../types/map3d'

export const useMap3DStore = defineStore('map3d', () => {
  const ready = ref(false)
  const loading = ref(false)
  const config = ref<Map3DConfig | null>(null)
  const entities = ref<Entity3D[]>([])
  const selectedEntity = ref<Entity3D | null>(null)
  const cameraPreset = ref<CameraPreset>('perspective')

  const layers = ref<LayerState>({
    buildings: true,
    roads: true,
    traffic: true,
    poi: true,
    crowd: false,
    labels: true,
  })

  const realtimeTraffic = ref<import('../types/map3d').RealtimeTrafficData[]>([])
  const realtimeCrowd = ref<import('../types/map3d').RealtimeCrowdData[]>([])
  const viewMode = ref<'3d' | '2d'>('3d')

  const hasConfig = computed(() => config.value !== null)
  const entityCount = computed(() => entities.value.length)

  async function loadConfig(): Promise<void> {
    try {
      config.value = await map3dApi.get3DConfig()
    } catch (e) {
      console.warn('[Map3D] 加载配置失败', e)
    }
  }

  async function loadEntities(): Promise<void> {
    loading.value = true
    try {
      const data = await map3dApi.get3DEntities()
      entities.value = data.entities || []
    } catch (e) {
      console.warn('[Map3D] 加载实体失败', e)
    } finally {
      loading.value = false
    }
  }

  function selectEntity(entity: Entity3D | null): void {
    selectedEntity.value = entity
  }

  function setPreset(preset: CameraPreset): void {
    cameraPreset.value = preset
  }

  function toggleLayer(key: keyof LayerState): void {
    layers.value[key] = !layers.value[key]
  }

  function setViewMode(mode: '3d' | '2d'): void {
    viewMode.value = mode
  }

  function setReady(val: boolean): void {
    ready.value = val
  }

  return {
    ready, loading, config, entities, selectedEntity,
    cameraPreset, layers, realtimeTraffic, realtimeCrowd,
    viewMode, hasConfig, entityCount,
    loadConfig, loadEntities, selectEntity, setPreset,
    toggleLayer, setViewMode, setReady,
  }
})
