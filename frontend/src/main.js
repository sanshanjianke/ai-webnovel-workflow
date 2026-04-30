import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

import Dashboard from './pages/Dashboard.vue'
import L1Seed from './pages/L1Seed.vue'
import L15Meeting from './pages/L15Meeting.vue'
import L2Meeting from './pages/L2Meeting.vue'
import L3Narrative from './pages/L3Narrative.vue'
import L4Render from './pages/L4Render.vue'
import WorldBook from './pages/WorldBook.vue'
import Settings from './pages/Settings.vue'
import Library from './pages/Library.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/l1', component: L1Seed },
  { path: '/l1-5', component: L15Meeting },
  { path: '/l2', component: L2Meeting },
  { path: '/l3', component: L3Narrative },
  { path: '/l4', component: L4Render },
  { path: '/worldbook', component: WorldBook },
  { path: '/library', component: Library },
  { path: '/settings', component: Settings }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const app = createApp(App)
app.use(router)
app.mount('#app')
