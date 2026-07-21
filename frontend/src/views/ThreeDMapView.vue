<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { useMap3DStore } from '../stores/map3d'
import { ThreeDMapEngine } from '../components/3d/ThreeDMapEngine'
import { MapSyncLayer } from '../components/3d/MapSyncLayer'
import { BuildingModule } from '../components/3d/BuildingModule'
import { RoadModule } from '../components/3d/RoadModule'
import { getTypeColor } from '../constants/entityTypes'
import * as THREE from 'three'
import type { Entity3D, CameraPreset, LayerState } from '../types/map3d'

const store = useMap3DStore()

// ── Refs ──
const containerRef = ref<HTMLDivElement>()
const loading = ref(true)
const loadError = ref('')
const statusText = ref('初始化中...')

// ── Engine instances ──
let engine: ThreeDMapEngine | null = null
let mapSync: MapSyncLayer | null = null
let buildingModule: BuildingModule | null = null
let roadModule: RoadModule | null = null
let raycaster: THREE.Raycaster | null = null
const mouse = new THREE.Vector2()

// 渲染循环计时（LOD 检查 / 路况刷新 / 脉冲动画）
let elapsed = 0
let lodTimer = 0
let trafficTimer = 0
const LOD_CHECK_INTERVAL = 1      // 秒
const TRAFFIC_REFRESH_INTERVAL = 3 // 秒

const buildingStyle = ref<'default' | 'warm' | 'cool' | 'night'>('warm')
const trafficEnabled = ref(true)

// ── 初始化 ──
async function initEngine() {
  if (!containerRef.value) return
  destroyEngine() // 重试时先清理旧实例
  loading.value = true
  loadError.value = ''
  statusText.value = '加载配置...'

  try {
    await store.loadConfig()
    if (!store.config?.enable_3d) {
      loadError.value = '3D 地图功能未启用'; loading.value = false; return
    }

    statusText.value = '初始化 3D 引擎...'
    raycaster = new THREE.Raycaster()
    raycaster.far = 8000

    engine = new ThreeDMapEngine({
      container: containerRef.value,
      backgroundColor: 0x16213e,
      fogFar: 10000,
      // 有底图时使用透明叠加模式，露出腾讯地图
      transparent: !!store.config.tencent_map_key,
    })

    // 地图同步层
    if (store.config.tencent_map_key) {
      mapSync = new MapSyncLayer({
        engine,
        mapKey: store.config.tencent_map_key,
        container: containerRef.value,
      })
      statusText.value = '加载腾讯地图...'
      await mapSync.loadMap()
      if (mapSync.ready) mapSync.enableSync()
    }

    // 加载实体 + 渲染建筑
    statusText.value = '加载实体数据...'
    await store.loadEntities()

    statusText.value = '生成 3D 建筑...'
    buildingModule = new BuildingModule(engine)
    if (store.entities.length > 0) {
      buildingModule.createFromEntities(store.entities)
    }

    statusText.value = '构建道路网络...'
    roadModule = new RoadModule(engine)
    roadModule.buildRoadNetwork()
    roadModule.updateTraffic(roadModule.generateSimulatedTraffic())

    // 绑定点击事件
    engine.renderer.domElement.addEventListener('click', onSceneClick)

    // 统一逐帧更新（挂载到引擎渲染循环，避免第二个 rAF 循环）
    engine.onBeforeRender = onFrameUpdate

    store.setReady(true)
    engine.start()

    statusText.value = ''
    loading.value = false
  } catch (e: any) {
    loadError.value = `初始化失败: ${e.message}`
    loading.value = false
  }
}

// ── 逐帧更新：LOD 检查 + 路况刷新 + 脉冲动画 ──
function onFrameUpdate(delta: number) {
  elapsed += delta
  lodTimer += delta
  trafficTimer += delta

  if (lodTimer >= LOD_CHECK_INTERVAL) {
    lodTimer = 0
    buildingModule?.updateLOD()
  }
  if (trafficTimer >= TRAFFIC_REFRESH_INTERVAL && roadModule) {
    trafficTimer = 0
    roadModule.updateTraffic(roadModule.generateSimulatedTraffic())
  }
  roadModule?.animatePulse(elapsed)
}

// ── 点击交互（Raycaster 拾取建筑） ──
function onSceneClick(event: MouseEvent) {
  if (!engine || !buildingModule || !raycaster) return
  const rect = engine.renderer.domElement.getBoundingClientRect()
  mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

  raycaster.setFromCamera(mouse, engine.camera)

  // 检测建筑点击
  if (store.layers.buildings) {
    const pickables = buildingModule.getPickables()
    if (pickables.length > 0) {
      const intersects = raycaster.intersectObjects(pickables, false)
      if (intersects.length > 0) {
        let obj: THREE.Object3D | null = intersects[0].object
        while (obj && !obj.userData?.entity) obj = obj.parent
        if (obj?.userData?.entity) {
          const entity = obj.userData.entity as Entity3D
          store.selectEntity(entity)
          engine.flyTo(entity.lng, entity.lat, 400)
          return
        }
      }
    }
  }

  // 未命中任何交互对象，取消选中
  store.selectEntity(null)
}

// ── 操作 ──
function setPreset(preset: CameraPreset) {
  store.setPreset(preset)
  engine?.setCameraPreset(preset)
}

function toggleLayer(key: keyof LayerState) {
  store.toggleLayer(key)
  switch (key) {
    case 'buildings':
      if (buildingModule) buildingModule.enabled = store.layers.buildings
      break
    case 'roads':
      if (roadModule) roadModule.roadsEnabled = store.layers.roads
      break
    case 'traffic':
      if (roadModule) roadModule.trafficEnabled = store.layers.traffic
      mapSync?.setTrafficVisible(store.layers.traffic)
      trafficEnabled.value = store.layers.traffic
      break
    case 'labels':
      if (engine) {
        engine.labelRenderer.domElement.style.display = store.layers.labels ? '' : 'none'
      }
      break
  }
}

function toggleViewMode() {
  const next = store.viewMode === '3d' ? '2d' : '3d'
  store.setViewMode(next)
  mapSync?.setPitch(next === '3d' ? 45 : 0)
}

function changeBuildingStyle(style: 'default' | 'warm' | 'cool' | 'night') {
  buildingStyle.value = style
  mapSync?.setBuildingStyle(style)
}

function flyToEntity(entity: Entity3D) {
  store.selectEntity(entity)
  engine?.flyTo(entity.lng, entity.lat, 600)
}

// ── 属性 ──
const categoryOptions = computed(() => {
  const types = new Set(store.entities.map(e => e.type))
  return Array.from(types).map(t => ({
    key: t,
    color: getTypeColor(t),
  }))
})

// ── 生命周期 ──
function destroyEngine() {
  if (engine) {
    engine.onBeforeRender = undefined
    engine.renderer.domElement.removeEventListener('click', onSceneClick)
  }
  mapSync?.dispose()
  buildingModule?.dispose()
  roadModule?.dispose()
  engine?.dispose()
  mapSync = null; buildingModule = null; roadModule = null; engine = null
  raycaster = null
  elapsed = 0; lodTimer = 0; trafficTimer = 0
  store.setReady(false)
}

onMounted(() => nextTick(() => initEngine()))

onUnmounted(() => destroyEngine())
</script>

<template>
  <div class="map3d-page">
    <!-- 3D 容器 -->
    <div ref="containerRef" class="map3d-container" />

    <!-- 加载状态 -->
    <Transition name="fade">
      <div v-if="loading" class="map3d-loading">
        <div class="loading-spinner"></div>
        <div class="loading-text">{{ statusText }}</div>
      </div>
    </Transition>

    <!-- 错误状态 -->
    <Transition name="fade">
      <div v-if="loadError" class="map3d-error">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.6;margin-bottom:12px"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        <div class="error-text">{{ loadError }}</div>
        <button class="btn btn-primary btn-sm" @click="initEngine">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
          重试
        </button>
      </div>
    </Transition>

    <!-- 顶部页头 -->
    <Transition name="slide-down">
      <div v-if="!loading && !loadError && store.ready" class="map3d-topbar">
        <div class="topbar-info">
          <h1 class="topbar-title">3D 智慧地图</h1>
          <span class="topbar-desc">白云区文旅三维可视化</span>
        </div>
        <div class="topbar-actions">
          <button class="btn btn-ghost btn-sm" @click="toggleViewMode">
            <svg v-if="store.viewMode === '3d'" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
            <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
            {{ store.viewMode === '3d' ? '切换 2D' : '切换 3D' }}
          </button>
        </div>
      </div>
    </Transition>

    <!-- 控制面板 -->
    <Transition name="slide-in-right">
      <div v-if="!loading && !loadError && store.ready" class="map3d-controls">
        <!-- 视角预设 -->
        <div class="control-group">
          <div class="group-title">视角</div>
          <div class="btn-group">
            <button
              v-for="p in (['perspective', 'top-down', 'street-view'] as CameraPreset[])"
              :key="p"
              :class="['ctrl-btn', { active: store.cameraPreset === p }]"
              @click="setPreset(p)"
            >
              <svg v-if="p === 'perspective'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
              <svg v-else-if="p === 'top-down'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              {{ p === 'perspective' ? '俯瞰' : p === 'top-down' ? '顶视' : '街景' }}
            </button>
          </div>
        </div>

        <!-- 图层控制 -->
        <div class="control-group">
          <div class="group-title">图层</div>
          <label v-for="(val, key) in store.layers" :key="key" class="layer-toggle">
            <input type="checkbox" :checked="val" @change="toggleLayer(key as keyof LayerState)" />
            <span class="layer-label">{{ layerLabels[key as keyof typeof layerLabels] }}</span>
          </label>
        </div>

        <!-- 建筑风格 -->
        <div class="control-group">
          <div class="group-title">建筑风格</div>
          <div class="btn-group">
            <button
              v-for="s in (['warm', 'cool', 'default', 'night'] as const)"
              :key="s"
              :class="['ctrl-btn', { active: buildingStyle === s }]"
              @click="changeBuildingStyle(s)"
            >
              {{ styleLabels[s] }}
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 详情面板 -->
    <Transition name="slide-in-left">
      <div v-if="store.selectedEntity" class="map3d-detail-panel">
        <div class="detail-header">
          <div class="detail-title-wrap">
            <span class="detail-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            </span>
            <h3 class="detail-title">{{ store.selectedEntity.display_name }}</h3>
          </div>
          <button class="detail-close" @click="store.selectEntity(null)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <div class="detail-body">
          <div class="detail-row">
            <span class="detail-label">类型</span>
            <span class="detail-value">
              <span class="badge badge-primary">{{ store.selectedEntity.type }}</span>
            </span>
          </div>
          <div class="detail-row">
            <span class="detail-label">地址</span>
            <span class="detail-value">{{ store.selectedEntity.address || '暂无' }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">坐标</span>
            <span class="detail-value detail-mono">
              {{ store.selectedEntity.lat.toFixed(4) }}, {{ store.selectedEntity.lng.toFixed(4) }}
            </span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 图例 -->
    <Transition name="fade">
      <div v-if="!loading && !loadError && categoryOptions.length > 0" class="map3d-legend">
        <div class="legend-title">实体类型</div>
        <div class="legend-list">
          <div v-for="cat in categoryOptions.slice(0, 8)" :key="cat.key" class="legend-item">
            <span class="legend-dot" :style="{ background: cat.color }"></span>
            <span class="legend-label">{{ cat.key }}</span>
          </div>
        </div>
        <div class="legend-divider"></div>
        <div class="legend-title">路况</div>
        <div class="legend-list">
          <div class="legend-item">
            <span class="legend-dot" :style="{ background: 'var(--traffic-smooth)' }"></span>
            <span class="legend-label">畅通</span>
          </div>
          <div class="legend-item">
            <span class="legend-dot" :style="{ background: 'var(--traffic-slow)' }"></span>
            <span class="legend-label">缓行</span>
          </div>
          <div class="legend-item">
            <span class="legend-dot" :style="{ background: 'var(--traffic-congested)' }"></span>
            <span class="legend-label">拥堵</span>
          </div>
          <div class="legend-item">
            <span class="legend-dot" :style="{ background: 'var(--traffic-severe)' }"></span>
            <span class="legend-label">严重</span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 底部状态栏 -->
    <Transition name="slide-up">
      <div v-if="!loading && !loadError && store.ready" class="map3d-statusbar">
        <div class="status-item">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V7l8-4v18"/><path d="M19 21V11l-6-4"/></svg>
          建筑 <strong>{{ store.entities.length }}</strong>
        </div>
        <div class="status-item">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
          道路 <strong>11</strong>
        </div>
        <div class="status-item">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          路况 <strong>{{ trafficEnabled ? '实时' : '关闭' }}</strong>
        </div>
        <div class="status-item">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          LOD <strong>{{ store.cameraPreset }}</strong>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script lang="ts">
// 图层与风格标签（非响应式常量）
const layerLabels = {
  buildings: '三维建筑',
  roads: '道路网',
  traffic: '实时路况',
  poi: '标记点',
  crowd: '人流热力',
  labels: '名称标签',
} as const

const styleLabels = {
  warm: '暖色',
  cool: '冷色',
  default: '默认',
  night: '暗夜',
} as const
</script>

<style scoped>
.map3d-page {
  position: relative;
  width: 100%;
  height: calc(100vh - var(--header-height));
  overflow: hidden;
  background: var(--map-bg);
  border-radius: var(--radius-md);
  margin-top: var(--space-4);
}

.map3d-container {
  position: absolute;
  inset: 0;
}

/* ── 顶部页头 ── */
.map3d-topbar {
  position: absolute;
  top: var(--space-4);
  left: var(--space-4);
  right: var(--space-4);
  z-index: var(--z-controls);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--map-panel-strong);
  border: 1px solid var(--map-border);
  border-radius: var(--radius-md);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.topbar-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.topbar-title {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--map-text);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}
.topbar-desc {
  font-size: var(--text-xs);
  color: var(--map-text-muted);
}
.topbar-actions {
  display: flex;
  gap: var(--space-2);
}
.topbar-actions .btn {
  background: var(--map-panel);
  border: 1px solid var(--map-border);
  color: var(--map-text);
}
.topbar-actions .btn:hover {
  background: var(--map-hover);
  border-color: var(--map-border-strong);
}

/* ── 加载状态 ── */
.map3d-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: var(--z-overlay);
  background: var(--map-bg);
  color: var(--map-text);
  gap: var(--space-4);
}
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 2px solid var(--map-border-strong);
  border-top-color: var(--map-accent);
  border-radius: var(--radius-full);
  animation: spin 0.8s linear infinite;
}
.loading-text {
  font-size: var(--text-sm);
  color: var(--map-text-muted);
  letter-spacing: var(--tracking-wide);
}

/* ── 错误状态 ── */
.map3d-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: var(--z-overlay);
  background: var(--map-bg);
  color: var(--map-text);
  gap: var(--space-2);
}
.error-text {
  font-size: var(--text-sm);
  color: #fca5a5;
  margin-bottom: var(--space-3);
}

/* ── 控制面板 ── */
.map3d-controls {
  position: absolute;
  top: 80px;
  right: var(--space-4);
  z-index: var(--z-controls);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 200px;
}
.control-group {
  background: var(--map-panel-strong);
  border: 1px solid var(--map-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.group-title {
  font-size: 10px;
  color: var(--map-text-dim);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: var(--font-semibold);
  padding: 0 var(--space-1);
}
.btn-group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
.ctrl-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--map-text-muted);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
}
.ctrl-btn:hover {
  background: var(--map-hover);
  color: var(--map-text);
}
.ctrl-btn.active {
  background: var(--map-accent-bg);
  color: var(--map-accent);
  border-color: rgba(129, 140, 248, 0.3);
}
.layer-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-1);
  font-size: var(--text-xs);
  color: var(--map-text-muted);
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background var(--duration-fast) var(--ease-default);
}
.layer-toggle:hover {
  background: var(--map-hover);
}
.layer-toggle input {
  accent-color: var(--map-accent);
  cursor: pointer;
}
.layer-label {
  flex: 1;
}

/* ── 详情面板 ── */
.map3d-detail-panel {
  position: absolute;
  bottom: 56px;
  left: var(--space-4);
  z-index: var(--z-controls);
  width: 320px;
  background: var(--map-panel-strong);
  border: 1px solid var(--map-border-strong);
  border-radius: var(--radius-md);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
}
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--map-border);
}
.detail-title-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}
.detail-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: var(--map-accent-bg);
  color: var(--map-accent);
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}
.detail-title {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--map-text);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  color: var(--map-text-dim);
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all var(--duration-fast) var(--ease-default);
  flex-shrink: 0;
}
.detail-close:hover {
  background: var(--map-hover);
  color: var(--map-text);
}
.detail-body {
  padding: var(--space-3) var(--space-4);
}
.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--map-border);
  font-size: var(--text-xs);
}
.detail-row:last-child {
  border-bottom: none;
}
.detail-label {
  color: var(--map-text-dim);
  font-weight: var(--font-medium);
}
.detail-value {
  color: var(--map-text);
  text-align: right;
  max-width: 60%;
  overflow: hidden;
  text-overflow: ellipsis;
}
.detail-mono {
  font-family: var(--font-mono);
  font-size: 11px;
}

/* ── 图例 ── */
.map3d-legend {
  position: absolute;
  bottom: 56px;
  right: var(--space-4);
  z-index: var(--z-controls);
  width: 180px;
  background: var(--map-panel-strong);
  border: 1px solid var(--map-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.legend-title {
  font-size: 10px;
  color: var(--map-text-dim);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: var(--font-semibold);
  margin-bottom: var(--space-2);
}
.legend-list {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-1);
  margin-bottom: var(--space-2);
}
.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}
.legend-label {
  font-size: var(--text-xs);
  color: var(--map-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.legend-divider {
  height: 1px;
  background: var(--map-border);
  margin: var(--space-2) 0;
}

/* ── 底部状态栏 ── */
.map3d-statusbar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: var(--z-controls);
  display: flex;
  gap: var(--space-6);
  padding: var(--space-2) var(--space-4);
  background: var(--map-panel-strong);
  border-top: 1px solid var(--map-border);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}
.status-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--map-text-dim);
}
.status-item svg {
  color: var(--map-text-dim);
}
.status-item strong {
  color: var(--map-text);
  font-weight: var(--font-semibold);
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .map3d-controls {
    width: 180px;
  }
  .map3d-detail-panel {
    width: calc(100% - 32px);
    left: var(--space-4);
    right: var(--space-4);
  }
  .map3d-legend {
    display: none;
  }
  .map3d-statusbar {
    gap: var(--space-3);
    overflow-x: auto;
  }
}
</style>