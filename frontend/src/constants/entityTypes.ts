/**
 * 实体类型统一配置
 * 消除 6 处重复定义的颜色/图标/高度映射
 */

export interface EntityTypeConfig {
  key: string
  label: string
  color: string         // hex 字符串（CSS 用）
  colorValue: number    // 数值（Three.js 用）
  icon: string
  defaultHeight: number // 建筑默认高度（米）
}

export const ENTITY_TYPES: Record<string, EntityTypeConfig> = {
  'A级景区/旅游景点': { key: 'scenic',    label: '景区',   color: '#1565c0', colorValue: 0x1565c0, icon: '🏞️', defaultHeight: 10 },
  '公园':             { key: 'park',      label: '公园',   color: '#2e7d32', colorValue: 0x2e7d32, icon: '🌳', defaultHeight: 5 },
  '非物质文化遗产':   { key: 'heritage',  label: '非遗',   color: '#c62828', colorValue: 0xc62828, icon: '🎭', defaultHeight: 12 },
  '图书馆':           { key: 'library',   label: '图书馆', color: '#e65100', colorValue: 0xe65100, icon: '📚', defaultHeight: 25 },
  '文化站':           { key: 'culture',   label: '文化站', color: '#f57f17', colorValue: 0xf57f17, icon: '🏛️', defaultHeight: 15 },
  '星级酒店':         { key: 'hotel',     label: '酒店',   color: '#6a1b9a', colorValue: 0x6a1b9a, icon: '🏨', defaultHeight: 60 },
  '酒店':             { key: 'hotel2',    label: '住宿',   color: '#7c3aed', colorValue: 0x7c3aed, icon: '🏨', defaultHeight: 35 },
  '民宿':             { key: 'bnb',       label: '民宿',   color: '#00695c', colorValue: 0x00695c, icon: '🏠', defaultHeight: 12 },
  '充电站':           { key: 'charging',  label: '充电',   color: '#00838f', colorValue: 0x00838f, icon: '⚡', defaultHeight: 6 },
  '旅行社':           { key: 'agency',    label: '旅行社', color: '#1565c0', colorValue: 0x1565c0, icon: '✈️', defaultHeight: 20 },
  '街镇':             { key: 'town',      label: '街镇',   color: '#00acc1', colorValue: 0x00acc1, icon: '📍', defaultHeight: 18 },
  '未知':             { key: 'unknown',   label: '其他',   color: '#90a4ae', colorValue: 0x90a4ae, icon: '📌', defaultHeight: 15 },
}

// 后端知识图谱输出的是短类型键（见 /api/data/categories 的 key/label 对照），
// 补充别名映射，避免最大的几类实体全部落入灰色兜底
const TYPE_ALIASES: Record<string, string> = {
  '景点': 'A级景区/旅游景点',
  '非遗项目': '非物质文化遗产',
  '酒店': '星级酒店',
  '旅馆': '民宿',
  '活动': '图书馆',
  '服务点': '图书馆',
  '供电网点': '充电站',
}

function resolveType(type: string): EntityTypeConfig | undefined {
  return ENTITY_TYPES[type] ?? ENTITY_TYPES[TYPE_ALIASES[type]]
}

/** 类型是否为已知实体类型（含后端短键别名） */
export function isKnownEntityType(type: string): boolean {
  return resolveType(type) !== undefined
}

/** 获取类型颜色（hex 字符串） */
export function getTypeColor(type: string): string {
  return resolveType(type)?.color ?? ENTITY_TYPES['未知'].color
}

/** 获取类型颜色（数值，Three.js 用） */
export function getTypeColorValue(type: string): number {
  return resolveType(type)?.colorValue ?? ENTITY_TYPES['未知'].colorValue
}

/** 获取类型图标 */
export function getTypeIcon(type: string): string {
  return resolveType(type)?.icon ?? ENTITY_TYPES['未知'].icon
}

/** 获取建筑默认高度 */
export function getTypeHeight(type: string): number {
  return resolveType(type)?.defaultHeight ?? 15
}

/** 获取所有类型选项（用于下拉筛选） */
export function getTypeOptions(): { value: string; label: string; color: string }[] {
  return Object.entries(ENTITY_TYPES)
    .filter(([key]) => key !== '未知')
    .map(([key, cfg]) => ({ value: key, label: cfg.label, color: cfg.color }))
}
