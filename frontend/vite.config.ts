import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from "vite-tsconfig-paths";

// https://vite.dev/config/
export default defineConfig({
  build: {
    sourcemap: 'hidden',
    // 路由级代码分割 + 第三方库分块，避免单个 chunk 过大导致首屏慢
    rollupOptions: {
      output: {
        manualChunks: {
          // React 核心：路由、状态管理
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          // UI 库：antd 较大，独立分块
          'antd-vendor': ['antd', '@ant-design/icons'],
          // 编辑器/渲染：markdown、代码高亮
          'markdown-vendor': ['react-markdown', 'rehype-highlight', 'remark-gfm', 'highlight.js'],
        },
      },
    },
    // 单 chunk 警告阈值提高到 1MB（antd 等第三方库分块后单块仍较大）
    chunkSizeWarningLimit: 1024,
  },
  plugins: [
    react({
      babel: {
        plugins: [
          'react-dev-locator',
        ],
      },
    }),
    tsconfigPaths()
  ],
})
