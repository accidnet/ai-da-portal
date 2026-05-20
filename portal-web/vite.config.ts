import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    // 라우트/차트 lazy loading 후 남는 echarts vendor chunk 기준으로 경고선을 조정합니다.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // 무거운 차트 의존성은 분석 화면 코드와 분리해 브라우저 캐싱 효율을 높입니다.
          if (id.includes('/node_modules/echarts/')) return 'vendor-echarts'
          if (id.includes('/node_modules/zrender/')) return 'vendor-zrender'
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
