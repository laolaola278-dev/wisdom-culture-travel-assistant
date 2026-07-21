/**
 * ThreeDMapEngine — Three.js 3D 场景引擎封装
 * 管理场景、渲染器、光照、天空盒和动画循环
 */
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import type { CameraPreset } from '../../types/map3d'
import { wgs84ToLocal } from '../../utils/coordinateUtils'

export interface EngineOptions {
  container: HTMLElement
  backgroundColor?: number
  fogColor?: number
  fogNear?: number
  fogFar?: number
  /** 透明模式：底图叠加时使用（canvas 透明，无地面/网格） */
  transparent?: boolean
}

export class ThreeDMapEngine {
  // 核心
  readonly scene: THREE.Scene
  readonly renderer: THREE.WebGLRenderer
  readonly labelRenderer: CSS2DRenderer
  readonly camera: THREE.PerspectiveCamera
  readonly controls: OrbitControls

  // 容器
  private container: HTMLElement
  private animationId = 0
  private _ready = false
  private _boundResize: () => void

  // 回调
  onBeforeRender?: (delta: number) => void
  onAfterRender?: (delta: number) => void

  constructor(options: EngineOptions) {
    const { container, backgroundColor, fogColor, fogNear, fogFar, transparent } = options
    this.container = container

    // ── Scene ──
    this.scene = new THREE.Scene()
    if (transparent) {
      // 底图叠加模式：canvas 透明，露出下方地图
      this.scene.background = null
    } else {
      this.scene.background = new THREE.Color(backgroundColor ?? 0x1a1a2e)
      // fogNear 提供时使用线性雾，否则使用指数雾
      this.scene.fog = fogNear != null
        ? new THREE.Fog(fogColor ?? 0x1a1a2e, fogNear, fogFar ?? 8000)
        : new THREE.FogExp2(fogColor ?? 0x1a1a2e, 1 / (fogFar ?? 8000))
    }

    // ── Camera ──
    this.camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / container.clientHeight,
      10,
      30000,
    )
    // 默认视角：45° 俯瞰白云区中心
    this.camera.position.set(0, 6000, 6000)
    this.camera.lookAt(0, 0, 0)

    // ── Renderer ──
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: !!transparent,
      powerPreference: 'high-performance',
    })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    this.renderer.setSize(container.clientWidth, container.clientHeight)
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap
    this.renderer.outputColorSpace = THREE.SRGBColorSpace
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.renderer.toneMappingExposure = 1.0
    container.appendChild(this.renderer.domElement)

    // ── Label Renderer (CSS2D) ──
    this.labelRenderer = new CSS2DRenderer()
    this.labelRenderer.setSize(container.clientWidth, container.clientHeight)
    this.labelRenderer.domElement.style.position = 'absolute'
    this.labelRenderer.domElement.style.top = '0'
    this.labelRenderer.domElement.style.pointerEvents = 'none'
    container.appendChild(this.labelRenderer.domElement)

    // ── Controls ──
    this.controls = new OrbitControls(this.camera, this.renderer.domElement)
    this.controls.enableDamping = true
    this.controls.dampingFactor = 0.08
    this.controls.minDistance = 200
    this.controls.maxDistance = 15000
    this.controls.maxPolarAngle = Math.PI / 2.1  // 限制不能翻到底部
    this.controls.target.set(0, 0, 0)
    this.controls.update()

    // ── Resize ──
    this._boundResize = this._handleResize.bind(this)
    window.addEventListener('resize', this._boundResize)

    // ── Lighting ──
    this._setupLighting()

    // ── Ground plane（透明叠加模式下不需要） ──
    if (!transparent) this._setupGround()

    this._ready = true
  }

  private _setupLighting(): void {
    // 环境光
    const ambient = new THREE.AmbientLight(0x8899bb, 1.2)
    this.scene.add(ambient)

    // 主方向光（模拟太阳）
    const sun = new THREE.DirectionalLight(0xffffff, 2.5)
    sun.position.set(5000, 8000, 3000)
    sun.castShadow = true
    sun.shadow.mapSize.width = 2048
    sun.shadow.mapSize.height = 2048
    sun.shadow.camera.near = 100
    sun.shadow.camera.far = 20000
    sun.shadow.camera.left = -8000
    sun.shadow.camera.right = 8000
    sun.shadow.camera.top = 8000
    sun.shadow.camera.bottom = -8000
    sun.shadow.bias = -0.0001
    this.scene.add(sun)

    // 补光（消除暗面）
    const fill = new THREE.DirectionalLight(0x6688cc, 0.6)
    fill.position.set(-3000, 2000, -2000)
    this.scene.add(fill)
  }

  private _setupGround(): void {
    // 简易地面
    const groundGeo = new THREE.PlaneGeometry(40000, 40000)
    const groundMat = new THREE.MeshLambertMaterial({
      color: 0x2d4a22,
      transparent: true,
      opacity: 0.3,
    })
    const ground = new THREE.Mesh(groundGeo, groundMat)
    ground.rotation.x = -Math.PI / 2
    ground.position.y = -5
    ground.receiveShadow = true
    ground.name = 'ground'
    this.scene.add(ground)

    // 网格辅助线
    const grid = new THREE.GridHelper(20000, 40, 0x334455, 0x223344)
    grid.position.y = -4
    this.scene.add(grid)
  }

  /** 设置相机预设视角 */
  setCameraPreset(preset: CameraPreset): void {
    const target = new THREE.Vector3(0, 0, 0)
    switch (preset) {
      case 'top-down':
        this.camera.position.set(0, 10000, 100)
        break
      case 'street-view':
        this.camera.position.set(0, 100, 500)
        break
      case 'perspective':
        this.camera.position.set(4000, 4000, 4000)
        break
      case 'free':
      default:
        break
    }
    this.controls.target.copy(target)
    this.controls.update()
  }

  /** 飞向指定经纬度（带平滑过渡） */
  flyTo(lng: number, lat: number, altitude = 800): void {
    const [x, y, z] = wgs84ToLocal(lng, lat, 0)
    // 相机保持当前方位角，移动到目标上方
    const offset = this.camera.position.clone().sub(this.controls.target)
    offset.setLength(Math.max(altitude, this.controls.minDistance))
    this.controls.target.set(x, y, z)
    this.camera.position.set(x + offset.x, altitude, z + offset.z)
    this.controls.update()
  }

  /** 启动渲染循环（幂等，重复调用无副作用） */
  start(): void {
    if (this.animationId) return
    let lastTime = performance.now()
    const animate = () => {
      this.animationId = requestAnimationFrame(animate)
      const now = performance.now()
      const delta = (now - lastTime) / 1000
      lastTime = now

      this.onBeforeRender?.(delta)
      this.controls.update()
      this.renderer.render(this.scene, this.camera)
      this.labelRenderer.render(this.scene, this.camera)
      this.onAfterRender?.(delta)
    }
    animate()
  }

  /** 停止渲染 */
  stop(): void {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId)
      this.animationId = 0
    }
  }

  /** 销毁引擎 */
  dispose(): void {
    this.stop()
    window.removeEventListener('resize', this._boundResize)
    this.onBeforeRender = undefined
    this.onAfterRender = undefined
    this.controls.dispose()
    // 释放场景中剩余的 GPU 资源（地面、网格线等引擎自建对象）
    this.scene.traverse((obj) => {
      const mesh = obj as THREE.Mesh
      if (mesh.geometry) mesh.geometry.dispose()
      const material = (mesh as THREE.Mesh).material
      if (Array.isArray(material)) material.forEach(m => m.dispose())
      else material?.dispose()
    })
    this.scene.clear()
    this.renderer.dispose()
    this.labelRenderer.domElement.remove()
    this.renderer.domElement.remove()
    this._ready = false
  }

  private _handleResize(): void {
    const w = this.container.clientWidth
    const h = this.container.clientHeight
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
    this.renderer.setSize(w, h)
    this.labelRenderer.setSize(w, h)
  }

  get ready(): boolean { return this._ready }
}