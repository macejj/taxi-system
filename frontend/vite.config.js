import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 开发环境下把 /api 转发到 FastAPI 后端，避免跨域配置
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // 后端自带的 Swagger 接口文档
      '/docs': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/openapi.json': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 体积较大的第三方库单独分包，避免单个 chunk 过大
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('echarts') || id.includes('zrender')) return 'vendor-echarts'
          if (id.includes('element-plus') || id.includes('@element-plus')) return 'vendor-element'
          if (id.includes('vue') || id.includes('@vue')) return 'vendor-vue'
          return 'vendor'
        },
      },
    },
  },
})
