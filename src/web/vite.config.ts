import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ command }) => ({
  plugins: [react()],
  // 生产构建用**相对**基路径(`./assets/*`),这样同一份产物可运行在任意深度的
  // 子路径下:实际前缀由服务端注入的 `<base href>` 决定(subpath-deployment)。
  // 若写死 `/`,产物就只能在域名根路径部署。
  // dev server 保持 `'/'`(它不经过服务端注入,也没有 `<base>`)。
  base: command === 'build' ? './' : '/',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
}))
