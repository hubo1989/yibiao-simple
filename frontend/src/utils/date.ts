/**
 * 日期/时间格式化工具函数
 */

/**
 * 将 ISO 日期字符串格式化为本地时间字符串（含年月日时分秒）
 */
export function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}
