<script setup lang="ts">
/**
 * Skeleton 骨架屏组件
 * 参考 shadcn/ui Skeleton
 */
withDefaults(defineProps<{
  width?: string
  height?: string
  rounded?: string
}>(), {
  rounded: 'var(--radius-sm)',
})
</script>

<template>
  <div
    class="skeleton"
    :style="{ width: width || '100%', height: height || '14px', borderRadius: rounded }"
  />
</template>
