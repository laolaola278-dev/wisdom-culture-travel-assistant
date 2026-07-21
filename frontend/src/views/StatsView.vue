<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getOverview, getLocationFrequency } from '../api/stats'
import { getTypeColor } from '../constants/entityTypes'
import { escapeHtml } from '../utils/escapeHtml'
import type { Overview, LocationFrequencyItem, TypeDistributionItem, DailyTrendItem } from '../types/stats'

const loading = ref(true)
const overview = ref<Overview>({ qa_total: 0, session_total: 0, user_total: 0, entity_total: 0 })
const topLocations = ref<LocationFrequencyItem[]>([])
const typeDistribution = ref<TypeDistributionItem[]>([])
const dailyTrend = ref<DailyTrendItem[]>([])

const barChartRef = ref<HTMLDivElement>()
const pieChartRef = ref<HTMLDivElement>()
const lineChartRef = ref<HTMLDivElement>()
let barChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null
let lineChart: echarts.ECharts | null = null

async function loadStats() {
  loading.value = true
  try {
    overview.value = await getOverview()
    const data = await getLocationFrequency(25)
    topLocations.value = data.top_locations || []
    typeDistribution.value = data.type_distribution || []
    dailyTrend.value = data.daily_trend || []
  } catch (e) {
    console.error('加载统计数据失败', e)
  } finally {
    loading.value = false
  }
  // 必须先退出 loading 让 v-else 分支挂载图表容器，再渲染
  await nextTick()
  renderCharts()
}

function getChartTextColor() {
  return getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim() || '#525252'
}
function getChartBorderColor() {
  return getComputedStyle(document.documentElement).getPropertyValue('--border-subtle').trim() || '#f5f5f5'
}

function renderCharts() {
  renderBarChart()
  renderPieChart()
  renderLineChart()
}

function renderBarChart() {
  if (!barChartRef.value) return
  if (barChart) barChart.dispose()
  barChart = echarts.init(barChartRef.value)

  const items = topLocations.value.slice(0, 20)
  const names = items.map(i => i.display_name || i.name)
  const values = items.map(i => i.count)
  const colors = items.map(i => getTypeColor(i.type))
  const textColor = getChartTextColor()

  barChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#e5e5e5',
      textStyle: { color: '#171717', fontSize: 12 },
      formatter: (p: any) => {
        const d = items[p[0].dataIndex]
        return `<b>${escapeHtml(d.display_name || d.name)}</b><br/>类型: ${escapeHtml(d.type)}<br/>提及: ${d.count}次`
      }
    },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { rotate: 45, fontSize: 10, interval: 0, color: textColor },
      axisTick: { alignWithLabel: true },
      axisLine: { lineStyle: { color: getChartBorderColor() } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { lineStyle: { color: getChartBorderColor() } },
    },
    dataZoom: [{ type: 'inside', start: 0, end: 100 }],
    series: [{
      type: 'bar',
      data: values.map((v, i) => ({ value: v, itemStyle: { color: colors[i], borderRadius: [4, 4, 0, 0] } })),
      barMaxWidth: 24,
    }],
  })
}

function renderPieChart() {
  if (!pieChartRef.value) return
  if (pieChart) pieChart.dispose()
  pieChart = echarts.init(pieChartRef.value)

  const data = typeDistribution.value.map(d => ({ name: d.type, value: d.count }))
  const textColor = getChartTextColor()

  pieChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#e5e5e5',
      textStyle: { color: '#171717', fontSize: 12 },
    },
    legend: {
      orient: 'vertical', left: 'left', top: 'middle', type: 'scroll',
      textStyle: { fontSize: 11, color: textColor },
    },
    series: [{
      type: 'pie',
      radius: ['45%', '72%'],
      center: ['62%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: 'transparent', borderWidth: 2 },
      label: { show: true, formatter: '{d}%', fontSize: 11, color: textColor },
      labelLine: { length: 8, length2: 8 },
      data,
    }],
  })
}

function renderLineChart() {
  if (!lineChartRef.value) return
  if (lineChart) lineChart.dispose()
  lineChart = echarts.init(lineChartRef.value)

  const dates = dailyTrend.value.map(d => d.date)
  const counts = dailyTrend.value.map(d => d.count)
  const textColor = getChartTextColor()

  lineChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: '#d4d4d4' } },
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#e5e5e5',
      textStyle: { color: '#171717', fontSize: 12 },
    },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '8%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLabel: { rotate: 30, fontSize: 10, color: textColor },
      axisLine: { lineStyle: { color: getChartBorderColor() } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: textColor, fontSize: 11 },
      splitLine: { lineStyle: { color: getChartBorderColor() } },
    },
    series: [{
      type: 'line',
      data: counts,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2, color: '#5e6ad2' },
      itemStyle: { color: '#5e6ad2', borderWidth: 2, borderColor: '#fff' },
      areaStyle: {
        color: new (echarts as any).graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(94,106,210,0.25)' },
          { offset: 1, color: 'rgba(94,106,210,0.01)' },
        ]),
      },
    }],
  })
}

function onResize() {
  barChart?.resize()
  pieChart?.resize()
  lineChart?.resize()
}

onMounted(() => {
  loadStats()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  barChart?.dispose()
  pieChart?.dispose()
  lineChart?.dispose()
})
</script>

<template>
  <div class="stats-page">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">数据分析</h1>
        <p class="page-desc">基于问答内容的地点热度与类型分布分析</p>
      </div>
    </div>

    <!-- 加载骨架屏 -->
    <template v-if="loading">
      <div class="overview-grid">
        <div v-for="i in 4" :key="i" class="stat-card">
          <div class="skeleton skeleton-avatar"></div>
          <div class="skeleton-info">
            <div class="skeleton" style="height:24px;width:60%;margin-bottom:8px;"></div>
            <div class="skeleton" style="height:12px;width:40%;"></div>
          </div>
        </div>
      </div>
      <div class="charts-grid">
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
      </div>
    </template>

    <template v-else>
      <!-- 概览卡片 -->
      <div class="overview-grid">
        <div class="stat-card">
          <div class="stat-icon" style="background:rgba(94,106,210,0.1);color:#5e6ad2;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ overview.qa_total }}</div>
            <div class="stat-label">总问答数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background:rgba(16,185,129,0.1);color:#10b981;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ overview.session_total }}</div>
            <div class="stat-label">会话总数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background:rgba(245,158,11,0.1);color:#f59e0b;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ overview.user_total }}</div>
            <div class="stat-label">注册用户</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background:rgba(239,68,68,0.1);color:#ef4444;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ overview.entity_total }}</div>
            <div class="stat-label">实体总数</div>
          </div>
        </div>
      </div>

      <!-- 图表区 -->
      <div class="charts-grid">
        <div class="chart-card">
          <div class="chart-header">
            <h3>地点提及次数 Top 20</h3>
            <span class="badge">柱状图</span>
          </div>
          <div ref="barChartRef" class="chart-box"></div>
        </div>
        <div class="chart-card">
          <div class="chart-header">
            <h3>类型分布</h3>
            <span class="badge">环形图</span>
          </div>
          <div ref="pieChartRef" class="chart-box"></div>
        </div>
      </div>

      <div class="chart-card full">
        <div class="chart-header">
          <h3>每日问答趋势</h3>
          <span class="badge">折线图</span>
        </div>
        <div ref="lineChartRef" class="chart-box"></div>
      </div>

      <!-- 数据表格 -->
      <div class="table-card">
        <div class="table-header">
          <h3>地点详细排行</h3>
          <span class="badge">{{ topLocations.length }} 条</span>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width:60px;">#</th>
                <th>地点名称</th>
                <th style="width:140px;">类型</th>
                <th style="width:100px;">提及次数</th>
                <th>地址</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in topLocations" :key="item.name">
                <td><span class="rank-num">{{ idx + 1 }}</span></td>
                <td class="cell-name">{{ item.display_name || item.name }}</td>
                <td>
                  <span class="type-tag" :style="{ background: getTypeColor(item.type) + '15', color: getTypeColor(item.type) }">
                    {{ item.type }}
                  </span>
                </td>
                <td class="cell-count">{{ item.count }}</td>
                <td class="cell-address">{{ item.address || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.stats-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* 页头 */
.page-header {
  margin-bottom: var(--space-1);
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

/* 概览卡片 */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}

.stat-card {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5);
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  transition: border-color var(--duration-fast) var(--ease-default);
}
.stat-card:hover {
  border-color: var(--border-strong);
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  flex-shrink: 0;
}

.stat-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1.2;
  letter-spacing: var(--tracking-tight);
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}

.skeleton-info { flex: 1; }

/* 图表 */
.charts-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--space-4);
}

.chart-card {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-5);
}
.chart-card.full { grid-column: 1 / -1; }

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}
.chart-header h3 {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.chart-box {
  width: 100%;
  height: 320px;
}

/* 表格 */
.table-card {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-subtle);
}
.table-header h3 {
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.data-table th {
  text-align: left;
  padding: var(--space-3) var(--space-5);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: var(--surface-secondary);
  border-bottom: 1px solid var(--border-default);
}

.data-table td {
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-primary);
}
.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: var(--surface-hover); }

.rank-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  background: var(--bg-muted);
  border-radius: var(--radius-sm);
}

.cell-name {
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.cell-count {
  font-weight: var(--font-semibold);
  color: var(--primary-600);
}
.dark .cell-count { color: var(--primary-300); }

.cell-address {
  color: var(--text-tertiary);
  font-size: var(--text-xs);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.type-tag {
  display: inline-block;
  padding: 2px var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  border-radius: var(--radius-xs);
}

@media (max-width: 900px) {
  .overview-grid { grid-template-columns: repeat(2, 1fr); }
  .charts-grid { grid-template-columns: 1fr; }
}
</style>
