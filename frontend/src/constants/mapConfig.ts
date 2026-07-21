/**
 * 地图配置常量
 */

export const MAP_CONFIG = {
  /** 白云区中心坐标 */
  center: {
    lng: 113.285,
    lat: 23.19,
  },
  /** 默认缩放级别 */
  defaultZoom: 12,
  /** 白云区近似边界 */
  bounds: {
    min: [113.15, 23.08] as [number, number],
    max: [113.55, 23.35] as [number, number],
  },
  /** 腾讯地图 JS API URL */
  tencentMapUrl: 'https://map.qq.com/api/gljs?v=1.exp',
  /** Leaflet CDN */
  leafletCssUrl: 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css',
  leafletJsUrl: 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js',
  /** 高德瓦片 URL 模板 */
  amapTileUrl: 'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
} as const
