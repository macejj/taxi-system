/**
 * 统一 API 层：按业务模块分组封装后端接口。
 * 所有函数返回 Promise，由 request 拦截器统一处理错误提示。
 */
import request from './request';

/* ------------------------------------------------------------------ 认证 */
export const authApi = {
  login: (data) => request.post('/auth/login', data),
  me: () => request.get('/auth/me'),
  changePassword: (data) => request.post('/auth/change-password', data),
  logout: () => request.post('/auth/logout'),
};

/* ------------------------------------------------------------------ 驾驶舱 */
export const dashboardApi = {
  summary: () => request.get('/dashboard/summary'),
  trend: (params) => request.get('/dashboard/trend', { params }),
  alerts: (params) => request.get('/dashboard/alerts', { params }),
  health: () => request.get('/dashboard/health'),
};

/* ------------------------------------------------------------------ 区域 */
export const regionApi = {
  page: (params) => request.get('/region/', { params }),
  all: () => request.get('/region/all'),
  types: () => request.get('/region/types'),
  detail: (id) => request.get(`/region/${id}`),
  create: (data) => request.post('/region/', data),
  update: (id, data) => request.put(`/region/${id}`, data),
  remove: (id) => request.delete(`/region/${id}`),
};

/* ------------------------------------------------------------------ 车辆 */
export const vehicleApi = {
  page: (params) => request.get('/vehicle/', { params }),
  all: () => request.get('/vehicle/all'),
  dictionaries: () => request.get('/vehicle/dictionaries'),
  detail: (id) => request.get(`/vehicle/${id}`),
  create: (data) => request.post('/vehicle/', data),
  update: (id, data) => request.put(`/vehicle/${id}`, data),
  updateStatus: (id, status) => request.patch(`/vehicle/${id}/status`, null, { params: { status } }),
  remove: (id) => request.delete(`/vehicle/${id}`),
};

/* ------------------------------------------------------------------ 驾驶员 */
export const driverApi = {
  page: (params) => request.get('/driver/', { params }),
  all: () => request.get('/driver/all'),
  detail: (id) => request.get(`/driver/${id}`),
  create: (data) => request.post('/driver/', data),
  update: (id, data) => request.put(`/driver/${id}`, data),
  remove: (id) => request.delete(`/driver/${id}`),
};

/* ------------------------------------------------------------------ 人车绑定 */
export const assignmentApi = {
  page: (params) => request.get('/assignment/', { params }),
  create: (data) => request.post('/assignment/', data),
  remove: (id) => request.delete(`/assignment/${id}`),
};

/* ------------------------------------------------------------------ 营运订单 */
export const operationApi = {
  page: (params) => request.get('/operation/', { params }),
  summary: (params) => request.get('/operation/summary', { params }),
  payTypes: () => request.get('/operation/pay-types'),
  detail: (id) => request.get(`/operation/${id}`),
  create: (data) => request.post('/operation/', data),
  update: (id, data) => request.put(`/operation/${id}`, data),
  remove: (id) => request.delete(`/operation/${id}`),
  importExcel: (formData) =>
    request.post('/operation/import-excel', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    }),
  templateUrl: '/api/operation/import/template',
  exportUrl: (params) => {
    const query = new URLSearchParams(
      Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ).toString();
    return `/api/operation/export/data${query ? `?${query}` : ''}`;
  },
};

/* ------------------------------------------------------------------ 叫车需求 */
export const demandApi = {
  page: (params) => request.get('/demand/', { params }),
  summary: (params) => request.get('/demand/summary', { params }),
  regionHourMatrix: (params) => request.get('/demand/region-hour-matrix', { params }),
  weekdayHour: (params) => request.get('/demand/weekday-hour', { params }),
  create: (data) => request.post('/demand/', data),
  remove: (id) => request.delete(`/demand/${id}`),
};

/* ------------------------------------------------------------------ 运营分析 */
export const analysisApi = {
  overview: (params) => request.get('/analysis/overview', { params }),
  incomeTrend: (params) => request.get('/analysis/income-trend', { params }),
  hourlyProfile: (params) => request.get('/analysis/hourly-profile', { params }),
  weekdayProfile: (params) => request.get('/analysis/weekday-profile', { params }),
  heatmap: (params) => request.get('/analysis/heatmap', { params }),
  regionRanking: (params) => request.get('/analysis/region-ranking', { params }),
  regionCompare: (params) => request.get('/analysis/region-compare', { params }),
  loadRate: (params) => request.get('/analysis/load-rate', { params }),
  driverRanking: (params) => request.get('/analysis/driver-ranking', { params }),
  vehicleEfficiency: (params) => request.get('/analysis/vehicle-efficiency', { params }),
  payType: (params) => request.get('/analysis/pay-type', { params }),
  weatherImpact: (params) => request.get('/analysis/weather-impact', { params }),
  abnormalAlert: (params) => request.get('/analysis/abnormal-alert', { params }),
  dashboard: (params) => request.get('/analysis/dashboard', { params }),
};

/* ------------------------------------------------------------------ 需求预测 */
export const forecastApi = {
  models: () => request.get('/forecast/models'),
  regions: () => request.get('/forecast/regions'),
  run: (data) => request.post('/forecast/run', data, { timeout: 300000 }),
  quick: (params) => request.get('/forecast/quick', { params, timeout: 300000 }),
  accuracy: (params) => request.get('/forecast/accuracy', { params }),
  history: (params) => request.get('/forecast/history', { params }),
  batch: (batchNo) => request.get(`/forecast/batch/${batchNo}`),
};

/* ------------------------------------------------------------------ 调度决策 */
export const dispatchApi = {
  regionStatus: (params) => request.get('/dispatch/region-status', { params }),
  generate: (data) => request.post('/dispatch/generate', data, { timeout: 300000 }),
  plans: (params) => request.get('/dispatch/plans', { params }),
  planDetail: (id) => request.get(`/dispatch/plans/${id}`),
  updatePlanStatus: (id, status) =>
    request.patch(`/dispatch/plans/${id}/status`, null, { params: { status } }),
  removePlan: (id) => request.delete(`/dispatch/plans/${id}`),
  orders: (params) => request.get('/dispatch/orders', { params }),
  feedback: (id, data) => request.post(`/dispatch/orders/${id}/feedback`, data),
  effect: (id) => request.get(`/dispatch/plans/${id}/effect`),
  strategyCompare: (params) => request.get('/dispatch/strategy-compare', { params, timeout: 300000 }),
  strategyBenchmark: (params) => request.get('/dispatch/strategy-benchmark', { params, timeout: 300000 }),
  statistics: (params) => request.get('/dispatch/statistics', { params }),
};

/* ------------------------------------------------------------------ 系统管理 */
export const systemApi = {
  users: (params) => request.get('/system/users', { params }),
  createUser: (data) => request.post('/system/users', data),
  updateUser: (id, data) => request.put(`/system/users/${id}`, data),
  resetPassword: (id, data) => request.post(`/system/users/${id}/reset-password`, data),
  removeUser: (id) => request.delete(`/system/users/${id}`),
  configs: () => request.get('/system/configs'),
  updateConfig: (key, value) =>
    request.put(`/system/configs/${key}`, { config_value: value }),
  reloadConfigs: () => request.post('/system/configs/reload'),
  logs: (params) => request.get('/system/logs', { params }),
  clearLogs: (params) => request.delete('/system/logs', { params }),
  dataStats: () => request.get('/system/data/stats'),
  simulate: (params) => request.post('/system/data/simulate', null, { params, timeout: 1800000 }),
  clearData: (params) => request.delete('/system/data/clear', { params }),
};

export default {
  authApi,
  dashboardApi,
  regionApi,
  vehicleApi,
  driverApi,
  assignmentApi,
  operationApi,
  demandApi,
  analysisApi,
  forecastApi,
  dispatchApi,
  systemApi,
};
