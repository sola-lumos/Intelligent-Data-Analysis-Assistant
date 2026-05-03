import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// echarts-for-react 会 bare import `tslib`；个别环境下 Vite 预构建链路解析失败，指向明确入口可避免 dev 报错
const tslibEs6 = path.resolve(__dirname, 'node_modules/tslib/tslib.es6.mjs')

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      tslib: tslibEs6,
    },
  },
  optimizeDeps: {
    include: ['tslib', 'echarts', 'echarts-for-react', 'zrender'],
  },
})
