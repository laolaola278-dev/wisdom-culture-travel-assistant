/**
 * HTML 转义：用于拼接 innerHTML 字符串（Leaflet popup、ECharts tooltip 等）
 * 的场景。实体名/类型等字段来自数据管道，须按不可信内容处理。
 */
export function escapeHtml(s: unknown): string {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string
  ))
}
