/**
 * 坐标转换工具
 * WGS-84 经纬度 ↔ Three.js 世界坐标（以白云区中心为原点）
 */

export const BAIYUN_CENTER = { lng: 113.285, lat: 23.19 }

/** 每度经度对应米数（在白云区纬度处） */
const METERS_PER_DEG_LNG = 111320 * Math.cos(BAIYUN_CENTER.lat * (Math.PI / 180))
/** 每度纬度对应米数 */
const METERS_PER_DEG_LAT = 111320

/** WGS84 经纬度 → Three.js 本地世界坐标 */
export function wgs84ToLocal(
  lng: number,
  lat: number,
  altitude = 0,
): [number, number, number] {
  const x = (lng - BAIYUN_CENTER.lng) * METERS_PER_DEG_LNG
  const z = (lat - BAIYUN_CENTER.lat) * METERS_PER_DEG_LAT // Z 轴朝北
  const y = altitude
  return [x, y, z]
}

/** Three.js 本地世界坐标 → WGS84 经纬度 */
export function localToWgs84(
  x: number,
  _y: number,
  z: number,
): [number, number] {
  const lng = x / METERS_PER_DEG_LNG + BAIYUN_CENTER.lng
  const lat = z / METERS_PER_DEG_LAT + BAIYUN_CENTER.lat
  return [lng, lat]
}

/** 墨卡托投影（腾讯地图格式）↔ WGS84 */
export function mercatorToWgs84(x: number, y: number): [number, number] {
  const lng = (x / 20037508.34) * 180
  let lat = (y / 20037508.34) * 180
  lat = (180 / Math.PI) * (2 * Math.atan(Math.exp((lat * Math.PI) / 180)) - Math.PI / 2)
  return [lng, lat]
}

export function wgs84ToMercator(lng: number, lat: number): [number, number] {
  const x = (lng * 20037508.34) / 180
  let y = Math.log(Math.tan(((90 + lat) * Math.PI) / 360)) / (Math.PI / 180)
  y = (y * 20037508.34) / 180
  return [x, y]
}

/** 获取白云区近似边界（WGS84） */
export function getBaiyunBounds(): { min: [number, number]; max: [number, number] } {
  return {
    min: [113.15, 23.08],
    max: [113.55, 23.35],
  }
}

/** 检查坐标是否在白云区范围内 */
export function isInBaiyun(lng: number, lat: number): boolean {
  const bounds = getBaiyunBounds()
  return (
    lng >= bounds.min[0] &&
    lng <= bounds.max[0] &&
    lat >= bounds.min[1] &&
    lat <= bounds.max[1]
  )
}

/** 两点间距离（米） */
export function distanceMeters(
  lng1: number, lat1: number,
  lng2: number, lat2: number,
): number {
  const dx = (lng2 - lng1) * METERS_PER_DEG_LNG
  const dy = (lat2 - lat1) * METERS_PER_DEG_LAT
  return Math.sqrt(dx * dx + dy * dy)
}

/** 将经纬度边界转为 Three.js 世界坐标边界 */
export function boundsToWorld(bounds: {
  min: [number, number]
  max: [number, number]
}): { min: [number, number, number]; max: [number, number, number] } {
  const [minX, , minZ] = wgs84ToLocal(bounds.min[0], bounds.min[1])
  const [maxX, , maxZ] = wgs84ToLocal(bounds.max[0], bounds.max[1])
  return { min: [minX, 0, minZ], max: [maxX, 0, maxZ] }
}