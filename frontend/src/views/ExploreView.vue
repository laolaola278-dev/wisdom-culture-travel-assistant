<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api/client'
import { API_ENDPOINTS } from '../constants/apiEndpoints'
import { useEntityTypes } from '../composables/useEntityTypes'
import { useMapInstance } from '../composables/useMapInstance'
import { escapeHtml } from '../utils/escapeHtml'
import Skeleton from '../components/Skeleton.vue'
import EmptyState from '../components/EmptyState.vue'

const route = useRoute()
const { getTypeInfo } = useEntityTypes()
const { mapReady, mapLoading, isAttached, initMap, addCircleMarker, clearMarkers, drawRoute, clearRoutes, fitToMarkers, destroy } = useMapInstance()

// ── State ────────────────────────────────────────────────────────
const activeTab = ref<'search' | 'entity' | 'ai' | 'map'>('map')
const query = ref('')
const loading = ref(false)
const categories = ref<{ key: string; label: string; count: number }[]>([])

// Search results
const searchResults = ref<any[]>([])
const searchError = ref('')

// Entity detail
const entity = ref<any>(null)
const entityNearby = ref<any[]>([])
const entityContext = ref<any>(null)
const entityLoading = ref(false)

// AI exploration
const aiQuery = ref('')
const aiResult = ref('')
const aiLoading = ref(false)

// ── Map State ────────────────────────────────────────────────────
const mapPoints = ref<any[]>([])
const activeCategory = ref('')
const routeStart = ref('')
const routeEnd = ref('')
const routePlanning = ref(false)
const routeResult = ref('')
const selectedPoint = ref<any>(null)
const nearbyPoints = ref<any[]>([])

// ── Methods ──────────────────────────────────────────────────────

async function loadCategories() {
  try {
    const data = await api.get<{ categories: typeof categories.value }>('/data/categories')
    categories.value = data.categories || []
  } catch { /* silent */ }
}

async function searchEntities() {
  const q = query.value.trim()
  if (!q) return
  loading.value = true
  searchError.value = ''
  searchResults.value = []
  try {
    const data = await api.get<{ results?: any[]; entities?: any[] }>('/graph/search', { q })
    searchResults.value = data.results || data.entities || []
    if (searchResults.value.length === 0) {
      searchError.value = '未找到匹配的实体'
    }
  } catch {
    searchError.value = '搜索失败，请重试'
  } finally {
    loading.value = false
  }
}

async function loadEntity(name: string) {
  entityLoading.value = true
  entity.value = null
  entityNearby.value = []
  entityContext.value = null
  activeTab.value = 'entity'
  try {
    const encName = encodeURIComponent(name)
    const [detail, nearby, context] = await Promise.all([
      api.get(`/explore/entity/${encName}/enhanced`).catch(() => null),
      api.get(`/explore/entity/${encName}/nearby`).catch(() => null),
      api.get(`/explore/entity/${encName}/context`).catch(() => null),
    ])
    if (detail) entity.value = detail
    if (nearby) entityNearby.value = (nearby as { nearby?: unknown[] }).nearby || []
    if (context) entityContext.value = context
    query.value = name
  } catch {
    searchError.value = '加载实体详情失败'
  } finally {
    entityLoading.value = false
  }
}

async function aiExplore() {
  const q = aiQuery.value.trim() || query.value.trim()
  if (!q) return
  aiLoading.value = true
  aiResult.value = ''
  try {
    const data = await api.post<{ answer?: string; result?: string }>('/explore/ai-search', { query: q, search_type: 'general' })
    aiResult.value = data.answer || data.result || JSON.stringify(data, null, 2)
  } catch {
    aiResult.value = 'AI探索失败，请重试'
  } finally {
    aiLoading.value = false
  }
}

// ── Map Methods ──────────────────────────────────────────────────

async function loadMapData() {
  try {
    const data = await api.get<{ points?: typeof mapPoints.value }>('/map/coordinates', { limit: 200 })
    mapPoints.value = data.points || []
    await initMap('explore-map')
    renderMapMarkers()
  } catch {
    /* mapReady 已在 composable 中处理 */
  }
}

function filteredPoints() {
  if (!activeCategory.value) return mapPoints.value
  return mapPoints.value.filter(p => p.type === activeCategory.value)
}

function renderMapMarkers() {
  nextTick(() => {
    const L = (window as any).L
    if (!L || !mapReady.value) return

    clearMarkers()
    const points = filteredPoints()
    points.forEach((p: any) => {
      const info = getTypeInfo(p.type)
      const popupHtml = `<div style="min-width:160px;line-height:1.7;">
        <b style="font-size:14px;color:${escapeHtml(info.color)};">${escapeHtml(info.icon)} ${escapeHtml(p.display_name || p.name)}</b><br>
        <span style="font-size:12px;color:#888;">${escapeHtml(p.type || '')}</span>
        ${p.location ? `<br><span style="font-size:11px;color:#aaa;">📍 ${escapeHtml(p.location)}</span>` : ''}
      </div>`
      const marker = addCircleMarker(p.lat, p.lng, info.color, popupHtml)
      if (marker) marker.on('click', () => { selectPoint(p) })
    })

    if (points.length > 0) {
      fitToMarkers()
    }
  })
}

function selectPoint(p: any) {
  selectedPoint.value = p
  loadNearbyForPoint(p)
}

async function loadNearbyForPoint(p: { name: string }) {
  nearbyPoints.value = []
  try {
    const data = await api.get<{ nearby?: typeof nearbyPoints.value }>(`/explore/entity/${encodeURIComponent(p.name)}/nearby`)
    nearbyPoints.value = (data.nearby || []).slice(0, 6)
  } catch { /* silent */ }
}

function setCategory(cat: string) {
  activeCategory.value = activeCategory.value === cat ? '' : cat
  renderMapMarkers()
}

async function planRoute() {
  const start = routeStart.value.trim()
  if (!start) return
  routePlanning.value = true
  routeResult.value = ''
  try {
    const data = await api.post<{ success?: boolean; route_plan?: string; waypoints?: unknown; message?: string }>(API_ENDPOINTS.explore.routePlan, {
      start,
      end: routeEnd.value.trim() || undefined,
      preferences: ['文化体验', '风景名胜'],
    })
    if (data.success) {
      routeResult.value = data.route_plan || '路线规划完成'
      if (data.waypoints && mapReady.value) {
        drawRoute(data.waypoints as any[])
      }
    } else {
      routeResult.value = data.message || '路线规划失败'
    }
  } catch {
    routeResult.value = '路线规划请求失败'
  } finally {
    routePlanning.value = false
  }
}

function clearRoute() {
  clearRoutes()
  routeResult.value = ''
}

// ── Lifecycle ────────────────────────────────────────────────────

onMounted(() => {
  loadCategories()
  // vue-router 已解码 query 参数，不能再 decodeURIComponent（含 % 的名称会抛 URIError）
  const entityParam = route.query.entity as string
  if (entityParam) {
    loadEntity(entityParam)
  }
  if (activeTab.value === 'map') {
    loadMapData()
  }
})

watch(() => route.query.entity, (val) => {
  if (val && typeof val === 'string') {
    loadEntity(val)
  }
})

watch(activeTab, (tab) => {
  if (tab !== 'map') return
  // v-if 切走会销毁地图 DOM；容器已分离时必须重新初始化而非仅补标记
  if (mapLoading.value) return
  if (!mapReady.value || !isAttached()) {
    loadMapData()
  } else {
    nextTick(() => renderMapMarkers())
  }
})

onUnmounted(() => {
  destroy()
})
</script>

<template>
  <div class="explore-page">
    <!-- 页头 -->
    <header class="page-header">
      <div>
        <h1 class="page-title">文旅探索</h1>
        <p class="page-desc">AI 智能检索 · 路线规划 · 附近推荐 · 深度文化探索</p>
      </div>
    </header>

    <!-- Tab 切换 -->
    <nav class="tab-nav">
      <button
        v-for="tab in [
          { key: 'map', label: '地图探索', icon: 'map' },
          { key: 'search', label: '实体搜索', icon: 'search' },
          { key: 'entity', label: '实体详情', icon: 'file', disabled: !entity },
          { key: 'ai', label: 'AI 探索', icon: 'sparkles' },
        ]"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        :disabled="tab.disabled"
        @click="activeTab = tab.key as typeof activeTab"
      >
        <svg v-if="tab.icon === 'map'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>
        <svg v-else-if="tab.icon === 'search'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <svg v-else-if="tab.icon === 'file'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        <svg v-else-if="tab.icon === 'sparkles'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z"/></svg>
        {{ tab.label }}
      </button>
    </nav>

    <!-- ── Map Tab ──────────────────────────────────────────────── -->
    <section v-if="activeTab === 'map'" class="tab-content">
      <!-- 搜索栏 -->
      <div class="search-row">
        <div class="search-input-wrap">
          <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            v-model="query"
            class="search-input"
            placeholder="输入景点名称或任意文旅关键词，AI 为您智能检索..."
            @keydown.enter.prevent="searchEntities"
          />
        </div>
        <button class="btn btn-primary" :disabled="aiLoading" @click="aiExplore">
          <svg v-if="!aiLoading" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z"/></svg>
          <span v-else class="loading-spinner loading-spinner-sm"></span>
          {{ aiLoading ? '检索中' : 'AI 检索' }}
        </button>
      </div>

      <!-- 快捷标签 -->
      <div class="quick-tags">
        <span class="tag-label">试试：</span>
        <button class="chip" @click="query = '白云山历史文化'; aiExplore()">白云山历史文化</button>
        <button class="chip" @click="query = '三元里附近景点'; aiExplore()">三元里附近景点</button>
        <button class="chip" @click="query = '非遗一日游路线'; aiExplore()">非遗一日游路线</button>
      </div>

      <!-- 地图 + 侧栏 -->
      <div class="map-layout">
        <!-- 地图区域 -->
        <div class="map-card">
          <div class="map-toolbar">
            <div class="toolbar-info">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/></svg>
              <span>地图视图 · <strong>{{ filteredPoints().length }}</strong> 个文旅点位</span>
            </div>
            <div class="toolbar-actions">
              <button class="btn btn-ghost btn-sm" @click="renderMapMarkers()">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>
                刷新
              </button>
              <button class="btn btn-ghost btn-sm" @click="clearRoute()">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                清除路线
              </button>
            </div>
          </div>
          <div id="explore-map" class="map-container">
            <div v-if="mapLoading" class="map-placeholder">
              <div class="loading-spinner"></div>
              <p class="placeholder-text">正在加载地图数据...</p>
            </div>
            <div v-else-if="!mapReady" class="map-placeholder">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.4;margin-bottom:8px"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <p class="placeholder-text">地图加载失败，请刷新重试</p>
            </div>
          </div>
        </div>

        <!-- 侧栏 -->
        <aside class="map-sidebar">
          <!-- AI 路线规划 -->
          <div class="sidebar-card">
            <div class="card-header">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>
              <h3 class="card-title">AI 路线规划</h3>
            </div>
            <p class="card-desc">基于知识图谱的智能路线推荐</p>
            <div class="form-stack">
              <div class="form-field">
                <label class="form-label">起点</label>
                <input v-model="routeStart" class="input" placeholder="例如：白云山风景名胜区" />
              </div>
              <div class="form-field">
                <label class="form-label">终点 <span class="form-optional">可选</span></label>
                <input v-model="routeEnd" class="input" placeholder="留空则自动推荐周边路线" />
              </div>
              <button class="btn btn-primary" :disabled="routePlanning" @click="planRoute">
                <span v-if="routePlanning" class="loading-spinner loading-spinner-sm"></span>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                {{ routePlanning ? '规划中' : '生成智能路线' }}
              </button>
            </div>
            <div v-if="routeResult" class="route-result">
              <div class="route-markdown route-plain">{{ routeResult }}</div>
            </div>
          </div>

          <!-- 附近推荐 -->
          <div class="sidebar-card">
            <div class="card-header">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              <h3 class="card-title">附近推荐</h3>
            </div>
            <p class="card-desc">点击地图点位查看关联景点</p>
            <div v-if="selectedPoint" class="nearby-list">
              <div class="nearby-header">{{ selectedPoint.display_name || selectedPoint.name }} 附近</div>
              <button
                v-for="(item, idx) in nearbyPoints"
                :key="idx"
                class="nearby-item"
                @click="loadEntity(item.name)"
              >
                <span class="nearby-dot" :style="{ background: getTypeInfo(item.type).color }"></span>
                <span class="nearby-name">{{ item.name }}</span>
                <span v-if="item.distance" class="nearby-dist">{{ item.distance }}km</span>
              </button>
              <div v-if="nearbyPoints.length === 0" class="nearby-empty">暂无附近推荐</div>
            </div>
            <div v-else class="nearby-empty">选择左侧景点后将展示附近关联推荐</div>
          </div>
        </aside>
      </div>

      <!-- 分类卡片 -->
      <div class="category-grid">
        <button
          v-for="cat in categories"
          :key="cat.key"
          :class="['category-card', { active: activeCategory === cat.key }]"
          @click="setCategory(cat.key)"
        >
          <div class="cat-icon">{{ getTypeInfo(cat.key).icon }}</div>
          <div class="cat-label">{{ cat.label }}</div>
          <div class="cat-count">{{ cat.count }} 条</div>
        </button>
      </div>
    </section>

    <!-- ── Search Tab ─────────────────────────────────────────── -->
    <section v-if="activeTab === 'search'" class="tab-content">
      <div class="search-row">
        <div class="search-input-wrap">
          <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input v-model="query" class="search-input" placeholder="输入景点名称、非遗项目、酒店、图书馆..." @keydown.enter.prevent="searchEntities" />
        </div>
        <button class="btn btn-primary" :disabled="loading" @click="searchEntities">
          <span v-if="loading" class="loading-spinner loading-spinner-sm"></span>
          {{ loading ? '搜索中' : '搜索' }}
        </button>
      </div>

      <div v-if="categories.length > 0" class="chip-row">
        <button
          v-for="cat in categories"
          :key="cat.key"
          class="chip"
          @click="query = cat.key; searchEntities()"
        >
          {{ cat.label }} · {{ cat.count }}
        </button>
      </div>

      <div v-if="searchError" class="error-banner">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        {{ searchError }}
      </div>

      <div v-if="loading" class="results-grid">
        <div v-for="i in 4" :key="i" class="result-card-skeleton">
          <Skeleton width="60%" height="16px" />
          <Skeleton width="40%" height="12px" />
        </div>
      </div>

      <div v-else-if="searchResults.length > 0" class="results-list">
        <button
          v-for="(item, idx) in searchResults"
          :key="idx"
          class="result-card"
          @click="loadEntity(item.name || item[0])"
        >
          <div class="result-info">
            <div class="result-name">{{ item.name || item[0] }}</div>
            <div class="result-meta">
              <span class="badge badge-primary">{{ item.type || item[1] || '未知类型' }}</span>
              <span v-if="item.score" class="result-score">匹配度 {{ (item.score * 100).toFixed(0) }}%</span>
            </div>
          </div>
          <svg class="result-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
      </div>

      <EmptyState
        v-else-if="!searchError"
        title="开始搜索文旅实体"
        description="输入景点名称、非遗项目或任意关键词"
      />
    </section>

    <!-- ── Entity Tab ──────────────────────────────────────────── -->
    <section v-if="activeTab === 'entity'" class="tab-content">
      <div v-if="entityLoading" class="entity-skeleton">
        <Skeleton width="40%" height="32px" />
        <Skeleton width="100%" height="20px" />
        <Skeleton width="100%" height="20px" />
        <Skeleton width="80%" height="20px" />
        <Skeleton width="60%" height="80px" />
      </div>

      <article v-else-if="entity" class="entity-detail">
        <header class="entity-header">
          <h2 class="entity-name">{{ entity.name || entity.entity }}</h2>
          <span class="badge badge-primary">{{ entity.type || entity.entity_type || '' }}</span>
        </header>

        <div v-if="entity.description || entity.intro" class="entity-section">
          <h4 class="section-title">简介</h4>
          <p class="section-text">{{ entity.description || entity.intro }}</p>
        </div>

        <div class="entity-grid">
          <div v-if="entity.address" class="entity-section">
            <h4 class="section-title">地址</h4>
            <p class="section-text">{{ entity.address }}</p>
          </div>
          <div v-if="entity.phone || entity.tel" class="entity-section">
            <h4 class="section-title">电话</h4>
            <p class="section-text">{{ entity.phone || entity.tel }}</p>
          </div>
          <div v-if="entity.hours || entity.open_time" class="entity-section">
            <h4 class="section-title">开放时间</h4>
            <p class="section-text">{{ entity.hours || entity.open_time }}</p>
          </div>
        </div>

        <div v-if="entity.tags && entity.tags.length" class="entity-section">
          <h4 class="section-title">标签</h4>
          <div class="tag-list">
            <span v-for="t in entity.tags" :key="t" class="badge">{{ t }}</span>
          </div>
        </div>

        <div v-if="entityContext" class="entity-section">
          <h4 class="section-title">关联图谱</h4>
          <div v-if="entityContext.relations && entityContext.relations.length" class="relations-list">
            <div v-for="(rel, idx) in entityContext.relations" :key="idx" class="relation-item">
              <span class="rel-type">{{ rel.relation || rel.type }}</span>
              <span class="rel-arrow">→</span>
              <button class="rel-target" @click="loadEntity(rel.target || rel.name)">{{ rel.target || rel.name }}</button>
            </div>
          </div>
          <div v-if="entityContext.attributes" class="attr-grid">
            <div v-for="(val, key) in entityContext.attributes" :key="key" class="attr-item">
              <span class="attr-key">{{ key }}</span>
              <span class="attr-value">{{ val }}</span>
            </div>
          </div>
        </div>

        <div v-if="entityNearby.length > 0" class="entity-section">
          <h4 class="section-title">周边推荐 · {{ entityNearby.length }}</h4>
          <div class="nearby-grid">
            <button
              v-for="(item, idx) in entityNearby"
              :key="idx"
              class="nearby-card"
              @click="loadEntity(item.name)"
            >
              <div class="nearby-card-name">{{ item.name }}</div>
              <div class="nearby-card-info">
                <span v-if="item.type">{{ item.type }}</span>
                <span v-if="item.distance"> · {{ item.distance }}km</span>
              </div>
            </button>
          </div>
        </div>
      </article>

      <EmptyState
        v-else
        title="请选择一个实体"
        description="通过搜索或地图点击查看实体详情"
      />
    </section>

    <!-- ── AI Tab ──────────────────────────────────────────────── -->
    <section v-if="activeTab === 'ai'" class="tab-content">
      <div class="search-row">
        <div class="search-input-wrap">
          <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z"/></svg>
          <input v-model="aiQuery" class="search-input" placeholder="用自然语言描述你想探索的内容..." @keydown.enter.prevent="aiExplore" />
        </div>
        <button class="btn btn-primary" :disabled="aiLoading" @click="aiExplore">
          <span v-if="aiLoading" class="loading-spinner loading-spinner-sm"></span>
          {{ aiLoading ? '探索中' : 'AI 探索' }}
        </button>
      </div>

      <div v-if="aiLoading" class="ai-result-card">
        <div class="ai-loading">
          <div class="typing-dots">
            <span></span><span></span><span></span>
          </div>
          <p class="typing-text">AI 正在思考...</p>
        </div>
      </div>

      <div v-else-if="aiResult" class="ai-result-card">
        <div class="ai-result-text">{{ aiResult }}</div>
      </div>

      <EmptyState
        v-else
        title="AI 智能探索"
        description="用自然语言提问，AI 帮你发现白云区文旅资源"
      />
    </section>
  </div>
</template>

<style scoped>
.explore-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

/* ── 页头 ── */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}
.page-title {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: 2px;
  letter-spacing: var(--tracking-tight);
}
.page-desc {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

/* ── Tab 导航 ── */
.tab-nav {
  display: inline-flex;
  gap: var(--space-1);
  padding: var(--space-1);
  background: var(--bg-muted);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  align-self: flex-start;
}
.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
}
.tab-btn:hover:not(:disabled) {
  color: var(--text-primary);
}
.tab-btn.active {
  background: var(--surface-primary);
  color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}
.tab-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  animation: fadeIn var(--duration-slow) var(--ease-out);
}

/* ── 搜索栏 ── */
.search-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
.search-input-wrap {
  position: relative;
  flex: 1;
}
.search-icon {
  position: absolute;
  left: var(--space-3);
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-quaternary);
  pointer-events: none;
}
.search-input {
  width: 100%;
  padding: var(--space-3) var(--space-3) var(--space-3) var(--space-10);
  font-size: var(--text-sm);
  color: var(--text-primary);
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  outline: none;
  transition: all var(--duration-fast) var(--ease-default);
}
.search-input:hover {
  border-color: var(--border-strong);
}
.search-input:focus {
  border-color: var(--primary-500);
  box-shadow: var(--shadow-focus);
}
.search-input::placeholder {
  color: var(--text-quaternary);
}

/* ── 快捷标签 ── */
.quick-tags {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.tag-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.chip {
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  background: var(--bg-muted);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
}
.chip:hover {
  background: var(--primary-50);
  color: var(--primary-700);
  border-color: var(--primary-200);
}
.dark .chip:hover {
  background: rgba(94, 106, 210, 0.15);
  color: var(--primary-300);
  border-color: rgba(94, 106, 210, 0.3);
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

/* ── 地图布局 ── */
.map-layout {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: var(--space-4);
}
@media (max-width: 1024px) {
  .map-layout {
    grid-template-columns: 1fr;
  }
}

.map-card {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.map-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-subtle);
}
.toolbar-info {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.toolbar-info strong {
  color: var(--text-primary);
  font-weight: var(--font-semibold);
}
.toolbar-actions {
  display: flex;
  gap: var(--space-1);
}
.map-container {
  height: 480px;
  background: var(--bg-muted);
}
.map-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
  gap: var(--space-3);
}
.placeholder-text {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

/* ── 侧栏 ── */
.map-sidebar {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.sidebar-card {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}
.card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-primary);
  margin-bottom: var(--space-1);
}
.card-title {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
}
.card-desc {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--space-3);
}

.form-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.form-label {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}
.form-optional {
  color: var(--text-quaternary);
  font-weight: var(--font-normal);
}

.route-result {
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  line-height: var(--leading-relaxed);
  color: var(--text-secondary);
  max-height: 200px;
  overflow-y: auto;
}
.route-plain {
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── 附近列表 ── */
.nearby-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.nearby-header {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--primary-500);
  margin-bottom: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-subtle);
}
.nearby-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition: background var(--duration-fast) var(--ease-default);
}
.nearby-item:hover {
  background: var(--surface-hover);
}
.nearby-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}
.nearby-name {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--text-primary);
}
.nearby-dist {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.nearby-empty {
  text-align: center;
  padding: var(--space-6) var(--space-3);
  color: var(--text-quaternary);
  font-size: var(--text-xs);
}

/* ── 分类卡片 ── */
.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--space-3);
}
.category-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-4) var(--space-3);
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
}
.category-card:hover {
  border-color: var(--primary-300);
  background: var(--primary-50);
  transform: translateY(-1px);
}
.dark .category-card:hover {
  background: rgba(94, 106, 210, 0.08);
  border-color: rgba(94, 106, 210, 0.4);
}
.category-card.active {
  border-color: var(--primary-500);
  background: var(--primary-50);
  box-shadow: var(--shadow-focus);
}
.dark .category-card.active {
  background: rgba(94, 106, 210, 0.12);
}
.cat-icon {
  font-size: 24px;
  line-height: 1;
}
.cat-label {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}
.cat-count {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

/* ── 错误提示 ── */
.error-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--error-bg);
  color: var(--error-text);
  border: 1px solid var(--error-border);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}

/* ── 搜索结果 ── */
.results-grid {
  display: grid;
  gap: var(--space-3);
}
.result-card-skeleton {
  padding: var(--space-4);
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.results-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.result-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-default);
  text-align: left;
  width: 100%;
}
.result-card:hover {
  border-color: var(--primary-300);
  background: var(--primary-50);
  transform: translateY(-1px);
}
.dark .result-card:hover {
  background: rgba(94, 106, 210, 0.06);
  border-color: rgba(94, 106, 210, 0.4);
}
.result-info {
  flex: 1;
  min-width: 0;
}
.result-name {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-1);
}
.result-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.result-score {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}
.result-arrow {
  color: var(--text-quaternary);
  transition: transform var(--duration-fast) var(--ease-default);
}
.result-card:hover .result-arrow {
  color: var(--primary-500);
  transform: translateX(2px);
}

/* ── 实体详情 ── */
.entity-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-6);
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
}
.entity-detail {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-6);
  animation: fadeIn var(--duration-slow) var(--ease-out);
}
.entity-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding-bottom: var(--space-4);
  margin-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-subtle);
}
.entity-name {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
  letter-spacing: var(--tracking-tight);
}

.entity-section {
  margin-bottom: var(--space-5);
}
.section-title {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: var(--tracking-wide);
  margin-bottom: var(--space-2);
  padding-left: var(--space-2);
  border-left: 2px solid var(--primary-500);
}
.section-text {
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  color: var(--text-secondary);
}

.entity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.relations-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.relation-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
}
.rel-type {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  background: var(--bg-muted);
  padding: 2px var(--space-2);
  border-radius: var(--radius-xs);
}
.rel-arrow {
  color: var(--text-quaternary);
}
.rel-target {
  color: var(--primary-500);
  background: none;
  border: none;
  cursor: pointer;
  font-size: var(--text-sm);
  padding: 0;
}
.rel-target:hover {
  text-decoration: underline;
}

.attr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-2);
}
.attr-item {
  display: flex;
  gap: var(--space-2);
  font-size: var(--text-sm);
  padding: var(--space-2);
  background: var(--bg-muted);
  border-radius: var(--radius-sm);
}
.attr-key {
  color: var(--text-tertiary);
  font-weight: var(--font-medium);
}
.attr-value {
  color: var(--text-secondary);
}

.nearby-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--space-2);
}
.nearby-card {
  padding: var(--space-3);
  background: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  cursor: pointer;
  text-align: left;
  transition: all var(--duration-fast) var(--ease-default);
}
.nearby-card:hover {
  background: var(--primary-50);
  border-color: var(--primary-300);
}
.dark .nearby-card:hover {
  background: rgba(94, 106, 210, 0.08);
  border-color: rgba(94, 106, 210, 0.3);
}
.nearby-card-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  margin-bottom: 2px;
}
.nearby-card-info {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

/* ── AI 结果 ── */
.ai-result-card {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-6);
}
.ai-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-8);
}
.typing-dots {
  display: flex;
  gap: var(--space-1);
}
.typing-dots span {
  width: 8px;
  height: 8px;
  background: var(--primary-500);
  border-radius: var(--radius-full);
  animation: bounce 1.4s infinite ease-in-out both;
}
.typing-dots span:nth-child(1) { animation-delay: -0.32s; }
.typing-dots span:nth-child(2) { animation-delay: -0.16s; }
.typing-text {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}
.ai-result-text {
  font-size: var(--text-sm);
  line-height: var(--leading-loose);
  color: var(--text-primary);
  white-space: pre-wrap;
}

/* ── Loading spinner ── */
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 2px solid var(--border-default);
  border-top-color: var(--primary-500);
  border-radius: var(--radius-full);
  animation: spin 0.8s linear infinite;
}
.loading-spinner-sm {
  width: 14px;
  height: 14px;
  border-width: 2px;
}

/* ── Leaflet 路线编号样式 ── */
:global(.route-number) {
  background: var(--primary-500) !important;
  color: #ffffff !important;
  border: none !important;
  font-size: var(--text-xs) !important;
  font-weight: var(--font-bold) !important;
  padding: 2px var(--space-1) !important;
  border-radius: var(--radius-full) !important;
}
</style>
