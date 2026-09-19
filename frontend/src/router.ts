import { createRouter, createWebHistory } from 'vue-router'
import Home from './pages/Home.vue'
import Manufacturing from './pages/Manufacturing.vue'
import WorkOrder from './pages/WorkOrder.vue'

const routes = [
  { path: '/', name: 'Home', component: Home },
  { path: '/manufacturing', name: 'Manufacturing', component: Manufacturing },
  { path: '/manufacturing/work-order', name: 'WorkOrder', component: WorkOrder }
]
const router = createRouter({
  history: createWebHistory('/frontend'),
  routes
})

export { router }