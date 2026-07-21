<template>
  <div class="about-page">
    <!-- 页头 -->
    <div class="page-header">
      <h1 class="page-title">关于项目</h1>
      <p class="page-desc">白云文化智能问答助手 · 智慧文旅平台</p>
    </div>

    <div class="about-grid">
      <!-- 项目简介 -->
      <section class="about-card">
        <div class="card-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
          </svg>
        </div>
        <h3 class="card-title">项目简介</h3>
        <p class="card-text">基于知识图谱的智慧文旅平台，致力于为游客提供智能问答、个性化推荐、路线规划等服务。</p>
      </section>

      <!-- 核心技术栈 -->
      <section class="about-card">
        <div class="card-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
          </svg>
        </div>
        <h3 class="card-title">核心技术栈</h3>
        <ul class="tech-list">
          <li><span class="tech-label">后端</span><span class="tech-value">Python · Flask · NetworkX · DeepSeek</span></li>
          <li><span class="tech-label">前端</span><span class="tech-value">Vue 3 · TypeScript · Vite · Pinia</span></li>
          <li><span class="tech-label">AI</span><span class="tech-value">多智能体 · Hybrid RAG · 三级回退</span></li>
          <li><span class="tech-label">数据</span><span class="tech-value">知识图谱 · 向量检索 · 高德 POI</span></li>
        </ul>
      </section>

      <!-- 版本信息 -->
      <section class="about-card">
        <div class="card-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
          </svg>
        </div>
        <h3 class="card-title">版本信息</h3>
        <div class="version-info">
          <span class="version-tag">v2.1</span>
          <span class="version-desc">多智能体 + 个性化推荐</span>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.about-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.page-header { margin-bottom: var(--space-1); }
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

.about-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-4);
}

.about-card {
  background: var(--surface-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  transition: border-color var(--duration-fast) var(--ease-default);
}
.about-card:hover {
  border-color: var(--border-strong);
}

.card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: var(--surface-selected);
  color: var(--primary-500);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-3);
}

.card-title {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.card-text {
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  color: var(--text-secondary);
}

.tech-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.tech-list li {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-subtle);
}
.tech-list li:last-child { border-bottom: none; }

.tech-label {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.tech-value {
  font-size: var(--text-sm);
  color: var(--text-primary);
}

.version-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.version-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--primary-600);
  background: var(--surface-selected);
  border-radius: var(--radius-xs);
}
.dark .version-tag { color: var(--primary-300); }

.version-desc {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
</style>
