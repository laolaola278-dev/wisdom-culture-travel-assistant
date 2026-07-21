/**
 * 实体类型 Composable
 * 封装 entityTypes 常量，提供响应式的类型查询能力
 */
import { getTypeColor, getTypeColorValue, getTypeHeight, getTypeOptions } from '../constants/entityTypes'

export interface TypeInfo {
  color: string
  icon: string
  label: string
}

// 扩展类型配置（含图标和短标签），用于 ExploreView 的地图标记
const typeInfoMap: Record<string, TypeInfo> = {
  'A级景区/旅游景点': { color: '#1565c0', icon: '⛰️', label: 'A级景区' },
  '公园': { color: '#2e7d32', icon: '🌳', label: '公园' },
  '非物质文化遗产': { color: '#c62828', icon: '🎭', label: '非遗' },
  '图书馆': { color: '#e65100', icon: '📚', label: '图书馆' },
  '文化站': { color: '#f57f17', icon: '🎪', label: '文化站' },
  '星级酒店': { color: '#6a1b9a', icon: '🏨', label: '星级酒店' },
  '民宿': { color: '#00695c', icon: '🏠', label: '民宿' },
  '充电站': { color: '#00838f', icon: '⚡', label: '充电站' },
  '旅行社': { color: '#1565c0', icon: '✈️', label: '旅行社' },
  '街镇': { color: '#00acc1', icon: '🏘️', label: '街镇' },
  // 后端知识图谱短类型键别名（/graph、/map、/stats 接口输出）
  '景点': { color: '#1565c0', icon: '⛰️', label: 'A级景区' },
  '非遗项目': { color: '#c62828', icon: '🎭', label: '非遗' },
  '酒店': { color: '#6a1b9a', icon: '🏨', label: '酒店' },
  '旅馆': { color: '#00695c', icon: '🏠', label: '旅馆' },
}

export function useEntityTypes() {
  function getTypeInfo(type: string): TypeInfo {
    return typeInfoMap[type] || { color: '#1a73e8', icon: '📍', label: type || '其他' }
  }

  return {
    getTypeColor,
    getTypeColorValue,
    getTypeHeight,
    getTypeOptions,
    getTypeInfo,
  }
}
