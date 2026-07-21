/**
 * LODManager — 细节层次管理器
 * 根据相机距离动态切换建筑/道路/标记的精度等级
 */
import * as THREE from 'three'
import type { LODLevel } from '../../types/map3d'
import { getTypeHeight, getTypeColorValue } from '../../constants/entityTypes'

export interface LODConfig {
  maxDistance: number
  levels: LODLevel[]
}

const DEFAULT_LOD_CONFIG: LODConfig = {
  maxDistance: 5000,
  levels: [
    { distance: 500,  buildingPrecision: 'fine',     textureResolution: 2048, labelVisible: true },
    { distance: 2000, buildingPrecision: 'extruded', textureResolution: 1024, labelVisible: true },
    { distance: 5000, buildingPrecision: 'box',      textureResolution: 512,  labelVisible: false },
    { distance: Infinity, buildingPrecision: 'none',  textureResolution: 0,    labelVisible: false },
  ],
}

export class LODManager {
  private config: LODConfig
  private currentLevel = 0
  private camera: THREE.PerspectiveCamera

  constructor(camera: THREE.PerspectiveCamera, config?: Partial<LODConfig>) {
    this.camera = camera
    this.config = { ...DEFAULT_LOD_CONFIG, ...config }
  }

  /** 根据相机到原点距离计算当前 LOD 等级 */
  getCurrentLOD(): { level: number; config: LODLevel } {
    const dist = this.camera.position.length()
    let level = 0
    for (let i = 0; i < this.config.levels.length; i++) {
      if (dist <= this.config.levels[i].distance) {
        level = i
        break
      }
    }
    this.currentLevel = level
    return { level, config: this.config.levels[level] }
  }

  /** 获取指定距离对应的 LOD 等级 */
  getLODForDistance(distance: number): LODLevel {
    for (const lvl of this.config.levels) {
      if (distance <= lvl.distance) return lvl
    }
    return this.config.levels[this.config.levels.length - 1]
  }

  /** 判断两个 LOD 等级是否发生变化 */
  hasChanged(): boolean {
    const dist = this.camera.position.length()
    let newLevel = 0
    for (let i = 0; i < this.config.levels.length; i++) {
      if (dist <= this.config.levels[i].distance) { newLevel = i; break }
    }
    const changed = newLevel !== this.currentLevel
    this.currentLevel = newLevel
    return changed
  }

  get configRef(): LODConfig { return this.config }
  get currentLevelIndex(): number { return this.currentLevel }
}

// 重新导出供 BuildingModule 使用
export { getTypeHeight, getTypeColorValue }