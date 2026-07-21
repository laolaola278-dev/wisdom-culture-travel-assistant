import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'qa', component: () => import('./views/QAView.vue') },
  { path: '/graph', name: 'graph', component: () => import('./views/GraphView.vue') },
  { path: '/explore', name: 'explore', component: () => import('./views/ExploreView.vue') },
  {
    path: '/map3d', name: 'map3d',
    component: () => import('./views/ThreeDMapView.vue'),
    meta: { requires3D: true },
  },
  {
    path: '/history', name: 'history',
    component: () => import('./views/HistoryView.vue'),
  },
  {
    path: '/favorites', name: 'favorites',
    component: () => import('./views/FavoritesView.vue'),
  },
  { path: '/stats', name: 'stats', component: () => import('./views/StatsView.vue') },
  { path: '/about', name: 'about', component: () => import('./views/AboutView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫：需要登录的页面自动跳转
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  if (to.meta.requiresAuth && !token) {
    next({ name: 'qa', query: { redirect: to.fullPath } })
  } else {
    next()
  }
})

export default router
