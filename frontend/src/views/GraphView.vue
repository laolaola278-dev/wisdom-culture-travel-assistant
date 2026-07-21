<script setup lang="ts">
import { ref, onMounted, watch, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { getGraphVisualization } from '../api/graph'
import { getTypeColor } from '../constants/entityTypes'
import { escapeHtml } from '../utils/escapeHtml'
import type { GraphNode, GraphEdge } from '../types/graph'

const loading = ref(true)
const entityType = ref('')
const nodes = ref<GraphNode[]>([])
const edges = ref<GraphEdge[]>([])
const chartRef = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

const categoryList = ref<string[]>([])

async function loadGraph() {
  loading.value = true
  try {
    const data = await getGraphVisualization(150, entityType.value || undefined)
    nodes.value = data.nodes || []
    edges.value = data.edges || []
    const types = new Set(nodes.value.map(n => n.category))
    categoryList.value = ['', ...Array.from(types)]
  } catch {
    console.error('加载知识图谱失败')
  } finally { loading.value = false }
  // 容器带 .hidden(display:none) 时 echarts.init 测得 0×0，
  // 必须先退出 loading 让容器可见再初始化
  await nextTick()
  renderChart()
}

function renderChart() {
  if (!chartRef.value) return
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  // 根据连接数计算节点大小
  const connectionCounts: Record<string, number> = {}
  edges.value.forEach((e: any) => {
    connectionCounts[e.source] = (connectionCounts[e.source] || 0) + 1
    connectionCounts[e.target] = (connectionCounts[e.target] || 0) + 1
  })

  const maxConn = Math.max(1, ...Object.values(connectionCounts))

  const graphNodes = nodes.value.map((n: GraphNode) => {
    const conn = connectionCounts[n.id] || 0
    const baseSize = n.category === '景点' || n.category === 'A级景区/旅游景点' || n.category === '非遗项目' ? 35 : 20
    const size = baseSize + (conn / maxConn) * 30
    return {
      id: n.id,
      name: n.label,
      category: n.category,
      symbolSize: Math.min(size, 60),
      itemStyle: { color: getTypeColor(n.category) },
      label: { show: conn >= 2 || size > 30, fontSize: 11, fontWeight: conn > 3 ? 'bold' : 'normal' },
      value: conn,
    }
  })

  const graphEdges = edges.value.map((e: any) => ({
    source: e.source,
    target: e.target,
    label: { show: false, formatter: e.relation, fontSize: 9 },
    lineStyle: { curveness: 0.15, width: 1.2, opacity: 0.5 },
  }))

  const usedCategories = Array.from(new Set(nodes.value.map((n: GraphNode) => n.category)))
  const categories = usedCategories.map(name => ({ name, itemStyle: { color: getTypeColor(name) } }))

  chart.setOption({
    title: { text: '白云区文旅知识图谱', left: 'center', top: 8, textStyle: { fontSize: 16, fontWeight: 'normal' } },
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => {
        if (p.dataType === 'node') {
          return `<b>${escapeHtml(p.name)}</b><br/>类型: ${escapeHtml(p.data?.category || '')}<br/>连接数: ${p.data?.value || 0}`
        }
        return `${escapeHtml(p.data?.source)} → ${escapeHtml(p.data?.target)}`
      }
    },
    legend: { data: categories.map(c => c.name), bottom: 8, type: 'scroll', textStyle: { fontSize: 11 } },
    animationDuration: 1500,
    animationEasingUpdate: 'quinticInOut',
    series: [{
      type: 'graph',
      layout: 'force',
      force: {
        repulsion: 600,
        edgeLength: [60, 180],
        gravity: 0.05,
        friction: 0.15,
      },
      roam: true,
      draggable: true,
      data: graphNodes,
      edges: graphEdges,
      categories,
      label: { position: 'bottom', fontSize: 10, distance: 4 },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [0, 6],
      lineStyle: { color: '#bbb', width: 1, curveness: 0.15, opacity: 0.5 },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 3, opacity: 0.8 },
        itemStyle: { shadowBlur: 20, shadowColor: 'rgba(0,0,0,0.2)' },
      },
      scaleLimit: { min: 0.3, max: 5 },
    }],
  })

  chart.on('click', (p: any) => {
    if (p.dataType === 'node' && p.data?.id) {
      window.open(`/explore?entity=${encodeURIComponent(p.data.id)}`, '_blank')
    }
  })
}

onMounted(loadGraph)
watch(entityType, loadGraph)

function onResize() { chart?.resize() }
window.addEventListener('resize', onResize)
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
})
</script>

<template>
  <div class="graph-page">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">知识图谱</h1>
        <p class="page-desc">文旅实体关系网络可视化</p>
      </div>
      <div class="header-actions">
        <select v-model="entityType" class="filter-select">
          <option value="">全部分类</option>
          <option v-for="t in categoryList.filter(Boolean)" :key="t" :value="t">{{ t }}</option>
        </select>
        <button class="btn btn-secondary btn-sm" @click="loadGraph">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          刷新
        </button>
      </div>
    </div>

    <!-- 图表卡片 -->
    <div class="chart-card">
      <div v-if="loading" class="loading-state">
        <div class="loading-spinner loading-spinner-lg"></div>
        <p class="loading-text">加载知识图谱...</p>
      </div>
      <div ref="chartRef" class="chart-area" :class="{ hidden: loading }"></div>
    </div>

    <!-- 底部信息 -->
    <div class="graph-footer">
      <div class="footer-stats">
        <span class="stat-item">
          <span class="stat-dot"></span>
          节点 <strong>{{ nodes.length }}</strong>
        </span>
        <span class="stat-item">
          <span class="stat-dot"></span>
          关系 <strong>{{ edges.length }}</strong>
        </span>
      </div>
      <span class="footer-hint">点击节点查看详情 · 滚轮缩放 · 拖拽移动</span>
    </div>
  </div>
</template>

<style scoped>
.graph-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}
.page-title {
  font-size: var(--text-xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: 2px;
}
.page-desc {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

.header-actions {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.filter-select {
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-primary);
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  outline: none;
  cursor: pointer;
  transition: border-color var(--duration-fast) var(--ease-default);
}
.filter-select:hover { border-color: var(--border-strong); }
.filter-select:focus { border-color: var(--primary-500); box-shadow: var(--shadow-focus); }

/* 图表卡片 */
.chart-card {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
  position: relative;
}

.loading-state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  background: var(--surface-primary);
  z-index: 1;
}

.loading-text {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

.chart-area {
  width: 100%;
  height: 600px;
}
.chart-area.hidden { display: none; }

/* 底部 */
.graph-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.footer-stats {
  display: flex;
  gap: var(--space-4);
}

.stat-item {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
.stat-item strong {
  color: var(--text-primary);
  font-weight: var(--font-semibold);
}

.stat-dot {
  width: 6px;
  height: 6px;
  background: var(--primary-500);
  border-radius: var(--radius-full);
}

.footer-hint {
  color: var(--text-quaternary);
}
</style>
