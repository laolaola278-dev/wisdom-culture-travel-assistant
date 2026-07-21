/**
 * BuildingModule — 三维建筑模型模块
 * 基于实体数据生成 Three.js 建筑体，支持 LOD 分级渲染
 *
 * 资源策略：几何体/材质按尺寸与颜色缓存共享，
 * clear() 仅移除场景对象，缓存资源在 dispose() 时统一释放。
 */
import * as THREE from 'three'
import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import type { ThreeDMapEngine } from './ThreeDMapEngine'
import { LODManager } from './LODManager'
import { isKnownEntityType, getTypeHeight, getTypeColorValue } from '../../constants/entityTypes'
import { wgs84ToLocal } from '../../utils/coordinateUtils'
import type { Entity3D, LODLevel } from '../../types/map3d'

export interface BuildingData {
  entity: Entity3D
  footprint?: [number, number][]    // 建筑轮廓 [lng, lat]
  floors?: number
  height?: number
}

/** 由实体 ID 生成确定性伪随机数（0~1），保证 LOD 重建时尺寸稳定 */
function seededRandom(seed: number): number {
  const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453
  return x - Math.floor(x)
}

export class BuildingModule {
  private engine: ThreeDMapEngine
  private lodManager: LODManager
  private buildings: THREE.Group
  private buildingMap: Map<number, THREE.Object3D> = new Map()
  private pickables: THREE.Object3D[] = []
  private _enabled = true

  // ── 共享资源缓存 ──
  private boxGeoCache: Map<string, THREE.BoxGeometry> = new Map()
  private planeGeoCache: Map<string, THREE.PlaneGeometry> = new Map()
  private edgeGeoCache: Map<string, THREE.EdgesGeometry> = new Map()
  private phongMatCache: Map<number, THREE.MeshPhongMaterial> = new Map()
  private lambertMatCache: Map<number, THREE.MeshLambertMaterial> = new Map()
  private readonly baseMat = new THREE.MeshLambertMaterial({ color: 0x666666 })
  private readonly roofMat = new THREE.MeshLambertMaterial({ color: 0x444444 })
  private readonly roofGeo = new THREE.ConeGeometry(1, 5, 4) // 单位半径，按建筑缩放
  private readonly windowMat = new THREE.MeshBasicMaterial({
    color: 0x87ceeb,
    transparent: true,
    opacity: 0.5,
  })
  private readonly edgeMat = new THREE.LineBasicMaterial({ color: 0x333333 })

  constructor(engine: ThreeDMapEngine) {
    this.engine = engine
    this.lodManager = new LODManager(engine.camera)

    this.buildings = new THREE.Group()
    this.buildings.name = 'Buildings'
    engine.scene.add(this.buildings)
  }

  /** 根据实体数据创建建筑群 */
  createFromEntities(entities: Entity3D[]): void {
    this.clear()

    const lod = this.lodManager.getCurrentLOD()
    // 已知类型的实体均生成建筑（未知类型跳过）
    const buildingEntities = entities.filter(e => isKnownEntityType(e.type))

    for (const entity of buildingEntities) {
      const mesh = this._createBuildingMesh(entity, lod.config)
      if (mesh) {
        this.buildings.add(mesh)
        this.buildingMap.set(entity.id, mesh)
      }
    }
    this._rebuildPickables()

    console.log(`[BuildingModule] 创建 ${this.buildingMap.size} 栋建筑`)
  }

  /** 生成单个建筑模型 */
  private _createBuildingMesh(entity: Entity3D, lodConfig: LODLevel): THREE.Group | null {
    if (lodConfig.buildingPrecision === 'none') return null

    const [cx, , cz] = wgs84ToLocal(entity.lng, entity.lat)
    const height = getTypeHeight(entity.type)
    const color = getTypeColorValue(entity.type)

    const group = new THREE.Group()
    group.name = `building-${entity.id}`
    group.position.set(cx, height / 2, cz)
    group.userData = { entity, type: 'building' }

    if (lodConfig.buildingPrecision === 'fine') {
      // LOD0: 精细化建筑（基座+主体+屋顶+窗户）
      this._buildDetailedMesh(group, entity, height, color, lodConfig.labelVisible)
    } else if (lodConfig.buildingPrecision === 'extruded') {
      // LOD1: 拉伸体（柱状建筑+轮廓线）
      this._buildExtrudedMesh(group, entity, height, color)
    } else {
      // LOD2: 简化 box
      this._buildBoxMesh(group, entity, height, color)
    }

    return group
  }

  // ── 缓存获取 ──

  private _getBoxGeo(w: number, h: number, d: number): THREE.BoxGeometry {
    const key = `${w}x${h}x${d}`
    let geo = this.boxGeoCache.get(key)
    if (!geo) {
      geo = new THREE.BoxGeometry(w, h, d)
      this.boxGeoCache.set(key, geo)
    }
    return geo
  }

  private _getPlaneGeo(w: number, h: number): THREE.PlaneGeometry {
    const key = `${w}x${h}`
    let geo = this.planeGeoCache.get(key)
    if (!geo) {
      geo = new THREE.PlaneGeometry(w, h)
      this.planeGeoCache.set(key, geo)
    }
    return geo
  }

  private _getEdgeGeo(boxGeo: THREE.BoxGeometry, key: string): THREE.EdgesGeometry {
    let geo = this.edgeGeoCache.get(key)
    if (!geo) {
      geo = new THREE.EdgesGeometry(boxGeo)
      this.edgeGeoCache.set(key, geo)
    }
    return geo
  }

  private _getPhongMat(color: number): THREE.MeshPhongMaterial {
    let mat = this.phongMatCache.get(color)
    if (!mat) {
      mat = new THREE.MeshPhongMaterial({ color, shininess: 30, specular: 0x111111 })
      this.phongMatCache.set(color, mat)
    }
    return mat
  }

  private _getLambertMat(color: number): THREE.MeshLambertMaterial {
    let mat = this.lambertMatCache.get(color)
    if (!mat) {
      mat = new THREE.MeshLambertMaterial({ color, flatShading: true })
      this.lambertMatCache.set(color, mat)
    }
    return mat
  }

  /** 确定性建筑平面尺寸 */
  private _footprint(entityId: number, baseW: number, varW: number, baseD: number, varD: number): [number, number] {
    const w = Math.round(baseW + seededRandom(entityId) * varW)
    const d = Math.round(baseD + seededRandom(entityId + 1) * varD)
    return [w, d]
  }

  /** LOD0: 精细建筑 */
  private _buildDetailedMesh(
    group: THREE.Group,
    entity: Entity3D,
    height: number,
    color: number,
    labelVisible: boolean,
  ): void {
    const [w, d] = this._footprint(entity.id, 20, 15, 15, 12)

    // 基座
    const base = new THREE.Mesh(this._getBoxGeo(w + 4, 3, d + 4), this.baseMat)
    base.position.y = -height / 2 + 1.5
    base.castShadow = true
    base.receiveShadow = true
    group.add(base)

    // 主体
    const body = new THREE.Mesh(this._getBoxGeo(w, height - 4, d), this._getPhongMat(color))
    body.position.y = 2
    body.castShadow = true
    body.receiveShadow = true
    group.add(body)

    // 屋顶（共享单位锥体，按建筑尺寸缩放）
    const roof = new THREE.Mesh(this.roofGeo, this.roofMat)
    roof.scale.set(Math.max(w, d) / 1.5, 1, Math.max(w, d) / 1.5)
    roof.position.y = height / 2 - 2.5
    roof.rotation.y = Math.PI / 4
    roof.castShadow = true
    group.add(roof)

    // 窗户条带（前后立面）
    const windowGeo = this._getPlaneGeo(Math.round(w * 0.8), 1.5)
    for (let floor = 0; floor < Math.floor(height / 4); floor++) {
      const wy = -height / 2 + 5 + floor * 4
      const winFront = new THREE.Mesh(windowGeo, this.windowMat)
      winFront.position.set(0, wy, d / 2 + 0.1)
      group.add(winFront)
      const winBack = new THREE.Mesh(windowGeo, this.windowMat)
      winBack.position.set(0, wy, -d / 2 - 0.1)
      winBack.rotation.y = Math.PI
      group.add(winBack)
    }

    // 标签
    if (labelVisible && entity.display_name) {
      const label = this._createLabel(entity.display_name, height)
      group.add(label)
    }
  }

  /** LOD1: 拉伸体建筑 */
  private _buildExtrudedMesh(
    group: THREE.Group,
    entity: Entity3D,
    height: number,
    color: number,
  ): void {
    const [w, d] = this._footprint(entity.id, 16, 12, 12, 10)

    const geo = this._getBoxGeo(w, height, d)
    const mesh = new THREE.Mesh(geo, this._getPhongMat(color))
    mesh.castShadow = true
    mesh.receiveShadow = true
    group.add(mesh)

    // 简易轮廓线
    const edges = new THREE.LineSegments(
      this._getEdgeGeo(geo, `${w}x${height}x${d}`),
      this.edgeMat,
    )
    group.add(edges)
  }

  /** LOD2: 简化 Box */
  private _buildBoxMesh(
    group: THREE.Group,
    _entity: Entity3D,
    height: number,
    color: number,
  ): void {
    const mesh = new THREE.Mesh(this._getBoxGeo(14, height, 12), this._getLambertMat(color))
    mesh.castShadow = true
    mesh.receiveShadow = true
    group.add(mesh)
  }

  /** 创建 CSS2D 文字标签 */
  private _createLabel(text: string, height: number): CSS2DObject {
    const div = document.createElement('div')
    div.textContent = text
    div.style.cssText = `
      color: #fff;
      font-size: 11px;
      font-weight: 500;
      background: rgba(0,0,0,0.6);
      padding: 2px 6px;
      border-radius: 3px;
      white-space: nowrap;
      pointer-events: none;
    `
    const label = new CSS2DObject(div)
    label.position.set(0, height / 2 + 8, 0)
    return label
  }

  /** 更新 LOD — 定期调用，等级变化时重建 */
  updateLOD(): void {
    if (!this._enabled) return
    if (!this.lodManager.hasChanged()) return
    this.rebuildWithLOD()
  }

  /** 按当前 LOD 重建所有建筑 */
  rebuildWithLOD(): void {
    const entities: Entity3D[] = []
    this.buildingMap.forEach((obj) => {
      if (obj.userData?.entity) entities.push(obj.userData.entity)
    })
    if (entities.length > 0) {
      this.createFromEntities(entities)
    }
  }

  /** Raycaster 拾取候选列表（含 entity userData 的建筑主体） */
  getPickables(): THREE.Object3D[] {
    return this.pickables
  }

  private _rebuildPickables(): void {
    this.pickables = []
    this.buildingMap.forEach((group) => {
      group.traverse((child) => {
        if (child instanceof THREE.Mesh) this.pickables.push(child)
      })
    })
  }

  /** 悬停高亮（材质为共享资源，高亮时替换为独立克隆） */
  highlight(id: number): void {
    const obj = this.buildingMap.get(id)
    if (!obj) return
    obj.traverse((child) => {
      if (child instanceof THREE.Mesh && !Array.isArray(child.material)) {
        const mat = child.material as THREE.MeshPhongMaterial
        if (!('emissive' in mat) || child.userData.origMaterial) return
        const clone = mat.clone()
        clone.emissive.set(0x333333)
        child.userData.origMaterial = mat
        child.material = clone
      }
    })
  }

  /** 取消高亮 */
  unhighlight(id: number): void {
    const obj = this.buildingMap.get(id)
    if (!obj) return
    obj.traverse((child) => {
      if (child instanceof THREE.Mesh && child.userData.origMaterial) {
        const clone = child.material as THREE.Material
        child.material = child.userData.origMaterial
        delete child.userData.origMaterial
        clone.dispose()
      }
    })
  }

  /** 获取指定 ID 的建筑 */
  getBuilding(id: number): THREE.Object3D | undefined {
    return this.buildingMap.get(id)
  }

  /** 清除所有建筑（共享几何/材质保留在缓存中，dispose() 时释放） */
  clear(): void {
    this.buildingMap.forEach((obj) => {
      this._restoreMaterials(obj)
      // 移除 CSS2D 标签的 DOM 节点
      obj.traverse((child) => {
        if (child instanceof CSS2DObject) child.element.remove()
      })
    })
    this.buildings.clear()
    this.buildingMap.clear()
    this.pickables = []
  }

  private _restoreMaterials(obj: THREE.Object3D): void {
    obj.traverse((child) => {
      if (child instanceof THREE.Mesh && child.userData.origMaterial) {
        ;(child.material as THREE.Material).dispose()
        child.material = child.userData.origMaterial
        delete child.userData.origMaterial
      }
    })
  }

  dispose(): void {
    this.clear()
    this.engine.scene.remove(this.buildings)
    // 统一释放缓存资源
    this.boxGeoCache.forEach(g => g.dispose())
    this.planeGeoCache.forEach(g => g.dispose())
    this.edgeGeoCache.forEach(g => g.dispose())
    this.phongMatCache.forEach(m => m.dispose())
    this.lambertMatCache.forEach(m => m.dispose())
    this.boxGeoCache.clear()
    this.planeGeoCache.clear()
    this.edgeGeoCache.clear()
    this.phongMatCache.clear()
    this.lambertMatCache.clear()
    this.roofGeo.dispose()
    this.baseMat.dispose()
    this.roofMat.dispose()
    this.windowMat.dispose()
    this.edgeMat.dispose()
  }

  get enabled(): boolean { return this._enabled }
  set enabled(v: boolean) {
    this._enabled = v
    this.buildings.visible = v
  }
}
