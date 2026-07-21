/**
 * API 端点常量
 * 注意：路径不含 /api 前缀（由 ApiClient 的 baseURL 统一添加）
 */

export const API_ENDPOINTS = {
  // 认证
  auth: {
    login: '/auth/login',
    register: '/auth/register',
    me: '/auth/me',
    refresh: '/auth/refresh',
    logout: '/auth/logout',
  },
  // 智能问答
  qa: {
    ask: '/v2/qa',
    stream: '/qa/stream',
    agents: '/v2/agents',
    recommend: '/v2/recommend',
    feedback: '/v2/feedback',
    hotQuestions: '/hot-questions',
  },
  // 知识图谱
  graph: {
    stats: '/graph/stats',
    visualization: '/graph/visualization',
    entity: (name: string) => `/graph/entity/${encodeURIComponent(name)}`,
    search: '/graph/search',
    entities: '/graph/entities',
  },
  // 文旅探索
  explore: {
    categories: '/data/categories',
    aiSearch: '/explore/ai-search',
    routePlan: '/explore/route-plan',
    entityEnhanced: (name: string) => `/explore/entity/${encodeURIComponent(name)}/enhanced`,
    entityNearby: (name: string) => `/explore/entity/${encodeURIComponent(name)}/nearby`,
    entityContext: (name: string) => `/explore/entity/${encodeURIComponent(name)}/context`,
    coordinates: '/map/coordinates',
  },
  // 历史记录
  history: {
    sessions: '/v2/sessions',
    sessionDetail: (id: string) => `/v2/sessions/${id}`,
    deleteSession: (id: string) => `/v2/sessions/${id}`,
    updateTitle: (id: string) => `/v2/sessions/${id}/title`,
  },
  // 收藏
  favorites: {
    list: '/v2/favorites',
    add: '/v2/favorites',
    remove: '/v2/favorites',
  },
  // 数据分析
  stats: {
    overview: '/stats/overview',
    locationFrequency: '/stats/location-frequency',
  },
  // 3D 地图
  map3d: {
    config: '/map/3d/config',
    entities: '/map/3d/entities',
    geocoder: '/map/proxy/geocoder',
    placeSearch: '/map/proxy/place/search',
    direction: '/map/proxy/direction',
  },
  // 系统
  system: {
    health: '/health',
    notice: '/notice',
    stats: '/system/stats',
  },
} as const
