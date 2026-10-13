/** 通用格式化与工具函数。 */

/** 数字千分位 */
export function thousands(value, digits = 0) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

/** 金额（元） */
export function money(value, digits = 2) {
  return thousands(value, digits);
}

/** 金额简写：12345 -> 1.23万 */
export function moneyShort(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  if (Math.abs(num) >= 100000000) return `${(num / 100000000).toFixed(2)}亿`;
  if (Math.abs(num) >= 10000) return `${(num / 10000).toFixed(2)}万`;
  return thousands(num, 0);
}

/** 百分比 */
export function percent(value, digits = 1) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '-';
  return `${num.toFixed(digits)}%`;
}

/** 环比变化：返回 { text, type }，type 用于着色 */
export function changeInfo(value, inverse = false) {
  const num = Number(value);
  if (!Number.isFinite(num)) return { text: '—', type: 'info' };
  const good = inverse ? num < 0 : num > 0;
  return {
    text: `${num > 0 ? '+' : ''}${num.toFixed(1)}%`,
    type: num === 0 ? 'info' : good ? 'success' : 'danger',
  };
}

/** 秒 -> 可读时长 */
export function duration(seconds) {
  const num = Number(seconds);
  if (!Number.isFinite(num)) return '-';
  if (num < 60) return `${num.toFixed(0)} 秒`;
  if (num < 3600) return `${(num / 60).toFixed(1)} 分钟`;
  return `${(num / 3600).toFixed(1)} 小时`;
}

/** 日期时间格式化 */
export function formatDateTime(value, withSeconds = false) {
  if (!value) return '-';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, '0');
  const base = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
  return withSeconds ? `${base}:${pad(date.getSeconds())}` : base;
}

/** 仅日期 */
export function formatDate(value) {
  if (!value) return '-';
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** 取最近 N 天的日期区间 [start, end]，格式 YYYY-MM-DD */
export function recentRange(days = 30) {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - (days - 1));
  return [formatDate(start), formatDate(end)];
}

/** 把 0-23 小时转成 HH:00 */
export function hourLabel(hour) {
  return `${String(hour).padStart(2, '0')}:00`;
}

/** 星期中文 */
export const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

/** 状态字典 */
export const VEHICLE_STATUS = {
  0: { text: '停运', type: 'info' },
  1: { text: '在营', type: 'success' },
  2: { text: '维修', type: 'warning' },
};

export const DRIVER_STATUS = {
  0: { text: '离职', type: 'info' },
  1: { text: '在职', type: 'success' },
  2: { text: '休假', type: 'warning' },
};

export const REQUEST_STATUS = {
  0: { text: '无人接单', type: 'danger' },
  1: { text: '已接单', type: 'warning' },
  2: { text: '已完成', type: 'success' },
  3: { text: '已取消', type: 'info' },
};

export const DISPATCH_STATUS = {
  0: { text: '待执行', type: 'warning' },
  1: { text: '执行中', type: 'primary' },
  2: { text: '已完成', type: 'success' },
  3: { text: '已拒绝', type: 'danger' },
  4: { text: '已取消', type: 'info' },
};

export const PLAN_STATUS = {
  0: { text: '草稿', type: 'info' },
  1: { text: '已下发', type: 'warning' },
  2: { text: '执行中', type: 'primary' },
  3: { text: '已完成', type: 'success' },
  4: { text: '已取消', type: 'info' },
};

export const ROLE_TEXT = {
  admin: '系统管理员',
  operator: '调度员',
  viewer: '只读用户',
};

/** 触发浏览器下载 */
export function download(url, filename) {
  const link = document.createElement('a');
  link.href = url;
  if (filename) link.download = filename;
  link.target = '_blank';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/** 带鉴权头的下载（导出接口需要 token） */
export function downloadWithAuth(url, filename) {
  const token = localStorage.getItem('token');
  fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    .then((response) => {
      if (!response.ok) throw new Error(`导出失败（${response.status}）`);
      return response.blob();
    })
    .then((blob) => {
      const href = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = href;
      link.download = filename || 'export';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(href);
    })
    .catch((error) => {
      // eslint-disable-next-line no-alert
      alert(error.message);
    });
}
