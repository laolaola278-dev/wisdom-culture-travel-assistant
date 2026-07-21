/**
 * Leaflet 地图实例管理 Composable
 * 抽取自 ExploreView.vue 中的地图初始化、标记、路线绘制逻辑
 */
import { ref, nextTick } from 'vue'
import { MAP_CONFIG } from '../constants/mapConfig'

export function useMapInstance() {
  const mapReady = ref(false)
  const mapLoading = ref(false)

  let mapInstance: any = null
  let mapMarkers: any[] = []
  let mapPolylines: any[] = []
  let leafletLoaded = false

  /**
   * 动态加载 Leaflet CDN（带失败与超时路径，避免 promise 永不 settle）
   */
  async function loadLeaflet(): Promise<void> {
    if (leafletLoaded && (window as any).L) return
    await new Promise<void>((resolve, reject) => {
      if ((window as any).L) { leafletLoaded = true; resolve(); return }
      const timer = window.setTimeout(() => reject(new Error('Leaflet 加载超时')), 15000)
      const css = document.createElement('link')
      css.rel = 'stylesheet'
      css.href = MAP_CONFIG.leafletCssUrl
      document.head.appendChild(css)
      const js = document.createElement('script')
      js.src = MAP_CONFIG.leafletJsUrl
      js.onload = () => { window.clearTimeout(timer); leafletLoaded = true; resolve() }
      js.onerror = () => { window.clearTimeout(timer); reject(new Error('Leaflet 加载失败')) }
      document.head.appendChild(js)
    })
  }

  /**
   * 地图容器是否仍在文档中（v-if 销毁后为 false）
   */
  function isAttached(): boolean {
    try {
      return !!(mapInstance && document.body.contains(mapInstance.getContainer()))
    } catch {
      return false
    }
  }

  /**
   * 初始化地图实例
   */
  async function initMap(containerId: string, center: [number, number] = [23.19, 113.285], zoom = 12): Promise<any> {
    mapLoading.value = true
    try {
      await loadLeaflet()
      await nextTick()
      const container = document.getElementById(containerId)
      if (!container) return null
      const L = (window as any).L
      if (!L) return null

      if (mapInstance) { mapInstance.remove(); mapInstance = null }
      mapMarkers = []
      mapPolylines = []

      mapInstance = L.map(container).setView(center, zoom)
      L.tileLayer(MAP_CONFIG.amapTileUrl, {
        subdomains: '1234',
        attribution: '高德地图',
        maxZoom: 18,
        minZoom: 4,
      }).addTo(mapInstance)

      mapReady.value = true
      return mapInstance
    } catch (e) {
      console.error('地图初始化失败', e)
      mapReady.value = false
      return null
    } finally {
      mapLoading.value = false
    }
  }

  /**
   * 添加圆形标记
   */
  function addCircleMarker(lat: number, lng: number, color: string, popupHtml?: string) {
    if (!mapInstance) return null
    const L = (window as any).L
    const marker = L.circleMarker([lat, lng], {
      radius: 9,
      fillColor: color,
      color: '#fff',
      weight: 2,
      fillOpacity: 0.9,
    }).addTo(mapInstance)
    if (popupHtml) marker.bindPopup(popupHtml)
    mapMarkers.push(marker)
    return marker
  }

  /**
   * 绘制路线（虚线 + 编号标记）
   */
  function drawRoute(waypoints: Array<{ lat?: number; lng?: number } | [number, number]>, color = '#1a73e8') {
    if (!mapInstance) return
    const L = (window as any).L
    if (!L || !waypoints.length) return

    clearRoutes()
    const latlngs = waypoints.map((p: any) => {
      if (Array.isArray(p)) return [p[1], p[0]]
      return [p.lat || p[1], p.lng || p[0]]
    })
    const polyline = L.polyline(latlngs, { color, weight: 5, opacity: 0.7, dashArray: '10,10' })
    polyline.addTo(mapInstance)
    mapPolylines.push(polyline)

    waypoints.forEach((p: any, i: number) => {
      const lat = Array.isArray(p) ? p[1] : (p.lat || p[1])
      const lng = Array.isArray(p) ? p[0] : (p.lng || p[0])
      const marker = L.circleMarker([lat, lng], {
        radius: 14, fillColor: color, color: '#fff', weight: 3, fillOpacity: 1,
      }).addTo(mapInstance)
      marker.bindTooltip((i + 1).toString(), { permanent: true, direction: 'center', className: 'route-number' })
      mapPolylines.push(marker)
    })

    mapInstance.fitBounds(polyline.getBounds().pad(0.15))
  }

  function clearRoutes() {
    if (!mapInstance) return
    mapPolylines.forEach((pl: any) => mapInstance.removeLayer(pl))
    mapPolylines = []
  }

  function clearMarkers() {
    if (!mapInstance) return
    mapMarkers.forEach((m: any) => mapInstance.removeLayer(m))
    mapMarkers = []
  }

  function fitToMarkers() {
    if (!mapInstance || mapMarkers.length === 0) return
    const L = (window as any).L
    const group = L.featureGroup(mapMarkers)
    mapInstance.fitBounds(group.getBounds().pad(0.1))
  }

  function destroy() {
    if (mapInstance) { mapInstance.remove(); mapInstance = null }
    mapMarkers = []
    mapPolylines = []
    mapReady.value = false
  }

  return {
    mapReady,
    mapLoading,
    mapInstance: () => mapInstance,
    isAttached,
    initMap,
    addCircleMarker,
    drawRoute,
    clearRoutes,
    clearMarkers,
    fitToMarkers,
    destroy,
  }
}
