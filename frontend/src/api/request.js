/**
 * axios 实例：统一注入令牌、统一错误提示。
 */
import axios from 'axios';
import { ElMessage } from 'element-plus';
import router from '../router';

const request = axios.create({
  baseURL: '/api',
  timeout: 60000,
});

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;

    if (status === 401) {
      localStorage.removeItem('token');
      if (router.currentRoute.value.name !== 'login') {
        router.push({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } });
      }
      ElMessage.error('登录已过期，请重新登录');
      return Promise.reject(error);
    }

    if (status === 403) {
      ElMessage.error(typeof detail === 'string' ? detail : '没有权限执行该操作');
      return Promise.reject(error);
    }

    if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请稍后重试（数据量较大时预测与仿真会耗时较久）');
      return Promise.reject(error);
    }

    if (!error.response) {
      ElMessage.error('无法连接后端服务，请确认后端已启动（默认 http://localhost:8000）');
      return Promise.reject(error);
    }

    let message = '请求失败';
    if (typeof detail === 'string') {
      message = detail;
    } else if (Array.isArray(detail) && detail.length) {
      // FastAPI 参数校验错误
      message = detail
        .map((item) => `${(item.loc || []).slice(1).join('.')}: ${item.msg}`)
        .join('；');
    }
    ElMessage.error(message);
    return Promise.reject(error);
  }
);

export default request;
