<script setup lang="ts">
/**
 * 全局 Toast 提示容器
 * 使用方式：在 App.vue 中引入 <ToastContainer />
 * 调用方式：const toast = useToast(); toast.success('保存成功')
 */
import { useToast } from '../composables/useToast'

const { toasts, dismiss } = useToast()

const iconMap: Record<string, string> = {
  success: '✓',
  error: '✕',
  warning: '!',
  info: 'i',
}
</script>

<template>
  <TransitionGroup name="toast" tag="div" class="toast-container">
    <div
      v-for="t in toasts"
      :key="t.id"
      :class="['toast-item', `toast-${t.type}`]"
      @click="dismiss(t.id)"
    >
      <span class="toast-icon">{{ iconMap[t.type] }}</span>
      <span class="toast-message">{{ t.message }}</span>
    </div>
  </TransitionGroup>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: var(--space-6);
  right: var(--space-6);
  z-index: var(--z-toast);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  min-width: 280px;
  max-width: 400px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  cursor: pointer;
  pointer-events: auto;
  font-size: var(--text-sm);
  color: var(--text-primary);
}

.toast-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-bold);
  color: #fff;
  flex-shrink: 0;
}

.toast-success .toast-icon { background: #10b981; }
.toast-error .toast-icon { background: #ef4444; }
.toast-warning .toast-icon { background: #f59e0b; }
.toast-info .toast-icon { background: var(--primary-500); }

.toast-message {
  flex: 1;
  line-height: var(--leading-normal);
}
</style>
