/**
 * MapSyncLayer — 腾讯地图 GL 底图 + Three.js 叠加层同步
 * 使用腾讯地图 JavaScript API GL 渲染 2.5D 底图，
 * 同步相机投影到 Three.js 场景
 */
import * as THREE from 'three'
import type { ThreeDMapEngine } from './ThreeDMapEngine'
import { BAIYUN_CENTER } from '../../utils/coordinateUtils'

export interface MapSyncOptions {
  engine: ThreeDMapEngine
  mapKey: string
  container: HTMLElement
}

export class MapSyncLayer {
  private engine: ThreeDMapEngine
  private mapKey: string
  private container: HTMLElement
  private mapContainer: HTMLDivElement
  private mapInstance: any = null
  private _ready = false
  private mapLoaded = false

  // 同步参数
  private syncEnabled = false
  private lastSyncTime = 0
  private syncInterval = 100 // ms

  constructor(options: MapSyncOptions) {
    this.engine = options.engine
    this.mapKey = options.mapKey
    this.container = options.container

    // 创建腾讯地图容器（位于 Three.js canvas 下方）
    this.mapContainer = document.createElement('div')
    this.mapContainer.id = 'tencent-map-container'
    this.mapContainer.style.cssText = `
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      z-index: 0;
      pointer-events: auto;
    `
    this.container.appendChild(this.mapContainer)

    // Three.js canvas 置于地图上方
    this.engine.renderer.domElement.style.position = 'absolute'
    this.engine.renderer.domElement.style.top = '0'
    this.engine.renderer.domElement.style.left = '0'
    this.engine.renderer.domElement.style.zIndex = '1'
    this.engine.renderer.domElement.style.pointerEvents = 'auto'

    // CSS2D 标签渲染器也置于上方
    this.engine.labelRenderer.domElement.style.zIndex = '2'
  }

  /** 加载腾讯地图 JS API */
  async loadMap(): Promise<void> {
    if (this.mapLoaded) return

    // 动态加载腾讯地图 GL JS
    await new Promise<void>((resolve, reject) => {
      if ((window as any).TMap) {
        this.mapLoaded = true
        resolve()
        return
      }
      const script = document.createElement('script')
      script.src = `https://map.qq.com/api/gljs?v=1.exp&key=${this.mapKey}`
      script.onload = () => {
        this.mapLoaded = true
        resolve()
      }
      script.onerror = () => reject(new Error('腾讯地图 API 加载失败'))
      document.head.appendChild(script)
    })

    await this._initMap()
  }

  private async _initMap(): Promise<void> {
    const TMap = (window as any).TMap
    if (!TMap) {
      console.warn('[MapSyncLayer] TMap 不可用，降级为纯 Three.js 模式')
      return
    }

    this.mapInstance = new TMap.Map(this.mapContainer, {
      center: new TMap.LatLng(BAIYUN_CENTER.lat, BAIYUN_CENTER.lng),
      zoom: 12,
      pitch: 45,
      rotation: 0,
      baseMap: {
        type: 'vector',
        features: ['base', 'building3d', 'point', 'label'],
      },
      mapStyleId: 'style1',
      showControl: false,
      viewMode: '3D',
    })

    // 启用 3D 建筑并设置显示范围
    try {
      if (this.mapInstance.setBuildingRange) {
        this.mapInstance.setBuildingRange([14, 20])
      }
      // 建筑颜色风格
      if (this.mapInstance.setMapStyleId) {
        setTimeout(() => {
          try { this.mapInstance.setMapStyleId('style2') } catch { /* */ }
        }, 500)
      }
    } catch { /* ignore */ }

    // 启用路况图层
    this._enableTrafficLayer()

    this._ready = true
    console.log('[MapSyncLayer] 腾讯地图初始化完成（含 3D 建筑 + 路况图层）')
  }

  /** 启用/切换路况图层 */
  private _enableTrafficLayer(): void {
    const TMap = (window as any).TMap
    if (!TMap || !this.mapInstance) return
    try {
      // 腾讯地图 GL 原生路况图层
      if (TMap.Traffic) {
        const trafficLayer = new TMap.Traffic({})
        trafficLayer.setMap(this.mapInstance)
        ;(this as any)._trafficLayer = trafficLayer
        console.log('[MapSyncLayer] 路况图层已启用')
      }
    } catch { /* 降级无路况图层 */ }
  }

  /** 切换路况图层可见性 */
  setTrafficVisible(visible: boolean): void {
    const layer = (this as any)._trafficLayer
    if (layer) {
      layer.setMap(visible ? this.mapInstance : null)
    }
  }

  /** 设置建筑颜色风格 */
  setBuildingStyle(style: 'default' | 'warm' | 'cool' | 'night'): void {
    if (!this.mapInstance) return
    const styleMap: Record<string, string> = {
      default: 'style1',
      warm: 'style2',
      cool: 'style3',
      night: 'style1',
    }
    try {
      this.mapInstance.setMapStyleId(styleMap[style] || 'style1')
    } catch { /* */ }
  }

  /** 设置地图倾斜角度 */
  setPitch(pitch: number): void {
    try { this.mapInstance?.setPitch(Math.max(0, Math.min(80, pitch))) } catch { /* */ }
  }

  /** 将 Three.js 相机同步到腾讯地图 */
  enableSync(): void {
    this.syncEnabled = true
    this.engine.onAfterRender = (delta) => {
      this._syncCameraToMap(delta)
    }
  }

  disableSync(): void {
    this.syncEnabled = false
  }

  private _syncCameraToMap(_delta: number): void {
    if (!this.syncEnabled || !this.mapInstance) return
    const now = performance.now()
    if (now - this.lastSyncTime < this.syncInterval) return
    this.lastSyncTime = now

    const cam = this.engine.camera
    const pos = cam.position
    const target = this.engine.controls.target

    // Three.js 世界坐标 → 经纬度
    const METERS_PER_DEG_LNG = 111320 * Math.cos(BAIYUN_CENTER.lat * Math.PI / 180)
    const METERS_PER_DEG_LAT = 111320

    const lng = pos.x / METERS_PER_DEG_LNG + BAIYUN_CENTER.lng
    const lat = pos.z / METERS_PER_DEG_LAT + BAIYUN_CENTER.lat

    const targetLng = target.x / METERS_PER_DEG_LNG + BAIYUN_CENTER.lng
    const targetLat = target.z / METERS_PER_DEG_LAT + BAIYUN_CENTER.lat

    const TMap = (window as any).TMap
    if (!TMap) return

    try {
      this.mapInstance.setCenter(new TMap.LatLng(targetLat, targetLng))

      // 根据相机高度估算 zoom level
      const alt = Math.max(pos.y, 100)
      const zoom = Math.max(10, Math.min(18, Math.round(20 - Math.log2(alt))))
      this.mapInstance.setZoom(zoom)

      // 俯仰角
      const pitch = Math.max(0, Math.min(80, 90 - (cam.position.y / Math.max(1, Math.sqrt(
        (cam.position.x - target.x) ** 2 + (cam.position.z - target.z) ** 2
      )) * 90 / 8000)))
      this.mapInstance.setPitch(pitch)
    } catch {
      /* 同步失败静默处理 */
    }
  }

  /** 获取地图实例 */
  getMap(): any {
    return this.mapInstance
  }

  /** 销毁 */
  dispose(): void {
    this.syncEnabled = false
    if (this.mapInstance) {
      this.mapInstance.destroy?.()
      this.mapInstance = null
    }
    this.mapContainer.remove()
  }

  get ready(): boolean { return this._ready }
}