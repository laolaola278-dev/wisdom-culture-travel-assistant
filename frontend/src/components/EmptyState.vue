<script setup lang="ts">
/**
 * 空状态组件
 * 参考 Linear/Notion 的空状态设计
 */
withDefaults(defineProps<{
  icon?: string
  title?: string
  description?: string
}>(), {
  icon: '📭',
  title: '暂无数据',
})
</script>

<template>
  <div class="empty-state animate-fade-in">
    <div class="empty-state-icon-wrap">
      <span class="empty-state-emoji">{{ icon }}</span>
    </div>
    <p class="empty-state-title">{{ title }}</p>
    <p v-if="description" class="empty-state-desc">{{ description }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-12) var(--space-6);
  text-align: center;
}

.empty-state-icon-wrap {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--space-4);
  background: var(--bg-muted);
  border-radius: var(--radius-full);
}

.empty-state-emoji {
  font-size: 28px;
  opacity: 0.6;
}

.empty-state-title {
  font-size: var(--text-md);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  margin-bottom: var(--space-1);
}

.empty-state-desc {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  max-width: 320px;
  line-height: var(--leading-relaxed);
}
</style>
