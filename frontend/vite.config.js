import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/assets/sr_connect/frontend/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    outDir: '../sr_connect/public/frontend',
    emptyOutDir: true,
    target: 'es2015',
    rollupOptions: {
      external: [
        /frappe-ui\/src\/components\/Spinner\.vue/
      ]
    }
  },
})
