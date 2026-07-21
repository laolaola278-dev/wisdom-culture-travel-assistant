/**
 * RoadModule — 道路网络 + 路况可视化模块
 * 绘制道路网络线, 实时路况颜色, 以及道路标注
 *
 * 资源策略：路况球体/光环几何与材质为共享资源，
 * updateTraffic 仅复位对象，不重复创建 GPU 资源。
 */
import * as THREE from 'three'
import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import type { ThreeDMapEngine } from './ThreeDMapEngine'
import { wgs84ToLocal } from '../../utils/coordinateUtils'
import type { RealtimeTrafficData } from '../../types/map3d'

/** 白云区主干道路模拟数据（经纬度路径） */
const BAIYUN_MAJOR_ROADS: { name: string; level: string; path: [number, number][] }[] = [
  { name: '白云大道北', level: 'highway', path: [[113.275, 23.22], [113.285, 23.20], [113.295, 23.18], [113.300, 23.16]] },
  { name: '机场路', level: 'highway', path: [[113.265, 23.22], [113.260, 23.19], [113.258, 23.17], [113.256, 23.15]] },
  { name: '广园中路', level: 'highway', path: [[113.24, 23.19], [113.28, 23.19], [113.32, 23.19]] },
  { name: '黄石东路', level: 'main', path: [[113.25, 23.20], [113.27, 23.20], [113.29, 23.20], [113.31, 23.20]] },
  { name: '同泰路', level: 'main', path: [[113.30, 23.205], [113.32, 23.200], [113.33, 23.198]] },
  { name: '新广从路', level: 'main', path: [[113.28, 23.21], [113.29, 23.20], [113.31, 23.19], [113.33, 23.18]] },
  { name: '大金钟路', level: 'secondary', path: [[113.278, 23.18], [113.282, 23.17], [113.285, 23.16]] },
  { name: '景从路', level: 'secondary', path: [[113.272, 23.17], [113.278, 23.17], [113.284, 23.17]] },
  { name: '白云三线', level: 'main', path: [[113.22, 23.18], [113.26, 23.18], [113.29, 23.18]] },
  { name: '陈田路', level: 'branch', path: [[113.285, 23.20], [113.288, 23.195]] },
  { name: '江夏路', level: 'branch', path: [[113.275, 23.19], [113.280, 23.19], [113.285, 23.19]] },
]

const ROAD_LEVEL_CONFIG: Record<string, { color: number; width: number; opacity: number }> = {
  highway:   { color: 0xff6600, width: 6, opacity: 0.9 },
  main:      { color: 0xffaa00, width: 4, opacity: 0.8 },
  secondary: { color: 0xcccccc, width: 2.5, opacity: 0.7 },
  branch:    { color: 0x999999, width: 1.5, opacity: 0.6 },
}

const TRAFFIC_COLORS: Record<string, number> = {
  smooth: 0x00c853,
  slow: 0xffd600,
  congested: 0xff6d00,
  severe: 0xd50000,
}

export class RoadModule {
  private engine: ThreeDMapEngine
  private roadGroup: THREE.Group
  private trafficGroup: THREE.Group
  private labelGroup: THREE.Group
  private _roadsEnabled = true
  private _trafficEnabled = true

  // ── 路况共享资源（按状态色缓存材质，几何体全局唯一） ──
  private readonly sphereGeo = new THREE.SphereGeometry(6, 8, 8)
  private readonly ringGeo = new THREE.RingGeometry(6, 12, 16)
  private sphereMats: Map<number, THREE.MeshBasicMaterial> = new Map()
  private ringMats: Map<number, THREE.MeshBasicMaterial> = new Map()

  constructor(engine: ThreeDMapEngine) {
    this.engine = engine

    this.roadGroup = new THREE.Group()
    this.roadGroup.name = 'Roads'
    engine.scene.add(this.roadGroup)

    this.trafficGroup = new THREE.Group()
    this.trafficGroup.name = 'Traffic'
    engine.scene.add(this.trafficGroup)

    this.labelGroup = new THREE.Group()
    this.labelGroup.name = 'RoadLabels'
    engine.scene.add(this.labelGroup)
  }

  /** 构建道路网络 */
  buildRoadNetwork(roads = BAIYUN_MAJOR_ROADS): void {
    this.clearRoads()

    for (const road of roads) {
      if (road.path.length < 2) continue
      this._drawRoadLine(road.path, road.level, road.name)
    }

    console.log(`[RoadModule] 构建 ${roads.length} 条道路`)
  }

  /** 绘制单条道路 */
  private _drawRoadLine(
    path: [number, number][],
    level: string,
    name: string,
  ): void {
    const config = ROAD_LEVEL_CONFIG[level] || ROAD_LEVEL_CONFIG.secondary
    const points3D = path.map(([lng, lat]) => {
      const [x, , z] = wgs84ToLocal(lng, lat, 0.5)
      return new THREE.Vector3(x, 0.5, z)
    })

    // 道路线条（实际道路面）
    const curve = new THREE.CatmullRomCurve3(points3D)
    const tubeGeo = new THREE.TubeGeometry(curve, path.length * 8, config.width, 4, false)
    const tubeMat = new THREE.MeshLambertMaterial({
      color: config.color,
      opacity: config.opacity,
      transparent: true,
      depthWrite: false,
    })
    const tube = new THREE.Mesh(tubeGeo, tubeMat)
    tube.renderOrder = 1
    this.roadGroup.add(tube)

    // 道路中心线（虚线效果）
    if (level === 'highway' || level === 'main') {
      const dashPoints = curve.getPoints(path.length * 6)
      const dashGeo = new THREE.BufferGeometry().setFromPoints(dashPoints)
      const dashMat = new THREE.LineDashedMaterial({
        color: level === 'highway' ? 0xffffff : 0xcccccc,
        dashSize: 10,
        gapSize: 8,
      })
      const dashLine = new THREE.Line(dashGeo, dashMat)
      dashLine.computeLineDistances()
      dashLine.position.y = 2
      this.roadGroup.add(dashLine)
    }

    // 道路名称标签（路径中点标注）
    const labelDiv = document.createElement('div')
    labelDiv.textContent = name
    labelDiv.style.cssText = `
      color: #fff;
      font-size: 10px;
      background: rgba(0,0,0,0.7);
      padding: 1px 5px;
      border-radius: 2px;
      white-space: nowrap;
      pointer-events: none;
    `
    const midIdx = Math.floor(points3D.length / 2)
    const label = new CSS2DObject(labelDiv)
    label.position.copy(points3D[midIdx])
    label.position.y += 12
    this.labelGroup.add(label)
  }

  private _getSphereMat(color: number): THREE.MeshBasicMaterial {
    let mat = this.sphereMats.get(color)
    if (!mat) {
      mat = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.8,
        depthWrite: false,
      })
      this.sphereMats.set(color, mat)
    }
    return mat
  }

  private _getRingMat(color: number): THREE.MeshBasicMaterial {
    let mat = this.ringMats.get(color)
    if (!mat) {
      mat = new THREE.MeshBasicMaterial({
        color,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.4,
        depthWrite: false,
      })
      this.ringMats.set(color, mat)
    }
    return mat
  }

  /** 更新路况数据（复用共享几何/材质，无 GPU 资源重建） */
  updateTraffic(data: RealtimeTrafficData[]): void {
    this.trafficGroup.clear()

    for (const item of data) {
      const [x, , z] = wgs84ToLocal(item.location[0], item.location[1], 1)
      const color = TRAFFIC_COLORS[item.status] || 0x999999

      // 路况点（发光球体）
      const sphere = new THREE.Mesh(this.sphereGeo, this._getSphereMat(color))
      sphere.position.set(x, 8, z)

      // 脉冲光环
      const ring = new THREE.Mesh(this.ringGeo, this._getRingMat(color))
      ring.rotation.x = -Math.PI / 2
      ring.position.y = 0.5
      sphere.add(ring)

      sphere.userData = { ...item, type: 'traffic' }
      this.trafficGroup.add(sphere)
    }
  }

  /** 路况光环脉动动画 — 每帧调用，elapsed 为累计秒数 */
  animatePulse(elapsed: number): void {
    if (!this._trafficEnabled) return
    const scale = 1 + Math.sin(elapsed * 3) * 0.2
    for (const child of this.trafficGroup.children) {
      const ring = child.children[0]
      if (ring) ring.scale.setScalar(scale)
    }
  }

  /** 生成模拟路况数据 */
  generateSimulatedTraffic(): RealtimeTrafficData[] {
    const statuses: RealtimeTrafficData['status'][] = ['smooth', 'slow', 'congested', 'severe']
    const points: [number, number][] = [
      [113.28, 23.20], [113.26, 23.19], [113.30, 23.18],
      [113.27, 23.17], [113.29, 23.195], [113.25, 23.185],
      [113.31, 23.21], [113.24, 23.17], [113.32, 23.19],
    ]

    return points.map(([lng, lat]) => ({
      location: [lng, lat] as [number, number],
      speed: Math.floor(Math.random() * 80),
      status: statuses[Math.floor(Math.random() * statuses.length)],
      timestamp: Date.now(),
    }))
  }

  /** 清除道路（道路几何/材质为独立资源，需释放） */
  clearRoads(): void {
    this._disposeGroup(this.roadGroup)
    this._clearLabels(this.labelGroup)
  }

  /** 清除所有 */
  clear(): void {
    this.clearRoads()
    this.trafficGroup.clear() // 路况资源为共享缓存，dispose() 时释放
  }

  /** 移除 CSS2D 标签及其 DOM 节点 */
  private _clearLabels(g: THREE.Group): void {
    g.traverse((child) => {
      if (child instanceof CSS2DObject) child.element.remove()
    })
    g.clear()
  }

  private _disposeGroup(g: THREE.Group): void {
    g.traverse((child) => {
      const mesh = child as THREE.Mesh
      if (child !== g && mesh.geometry) {
        mesh.geometry.dispose()
        if (Array.isArray(mesh.material)) {
          mesh.material.forEach(m => m.dispose())
        } else {
          mesh.material?.dispose()
        }
      }
    })
    g.clear()
  }

  dispose(): void {
    this.clear()
    this.engine.scene.remove(this.roadGroup)
    this.engine.scene.remove(this.trafficGroup)
    this.engine.scene.remove(this.labelGroup)
    // 释放路况共享资源
    this.sphereGeo.dispose()
    this.ringGeo.dispose()
    this.sphereMats.forEach(m => m.dispose())
    this.ringMats.forEach(m => m.dispose())
    this.sphereMats.clear()
    this.ringMats.clear()
  }

  get roadsEnabled(): boolean { return this._roadsEnabled }
  set roadsEnabled(v: boolean) {
    this._roadsEnabled = v
    this.roadGroup.visible = v
    this.labelGroup.visible = v
  }

  get trafficEnabled(): boolean { return this._trafficEnabled }
  set trafficEnabled(v: boolean) {
    this._trafficEnabled = v
    this.trafficGroup.visible = v
  }
}
