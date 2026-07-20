import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from "vite-tsconfig-paths";

// https://vite.dev/config/
export default defineConfig({
  build: {
    sourcemap: false,
    // 路由级代码分割：
    // - react-vendor：仅 react/react-dom/router 核心稳定库（精确匹配，避免误吞 @ant-design）
    // - antd 等交给 vite 自动 tree-shake 与分块，避免强制 manualChunks 导致整库打入
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            // 精确匹配 react 核心（路径以 react/ react-dom/ 等开头）
            // 避免匹配 @ant-design/icons、react-markdown 等"含 react 字样"的包
            if (
              id.includes('node_modules/react/') ||
              id.includes('node_modules/react-dom/') ||
              id.includes('node_modules/react-router/') ||
              id.includes('node_modules/react-router-dom/') ||
              id.includes('node_modules/scheduler/')
            ) {
              return 'react-vendor';
            }
          }
          return undefined;
        },
      },
    },
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
