import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

import Dashboard from './pages/Dashboard.vue'
import L1Seed from './pages/L1Seed.vue'
import Orchestration from './pages/Orchestration.vue'

import WorldBook from './pages/WorldBook.vue'
import Settings from './pages/Settings.vue'
import Library from './pages/Library.vue'
import ChatPopup from './pages/ChatPopup.vue'
import OutputPage from './pages/OutputPage.vue'
import ViewerPage from './pages/ViewerPage.vue'
import WorldBookManager from './pages/WorldBookManager.vue'
import RAGManager from './pages/RAGManager.vue'

const routes = [
  { path: '/', component: Dashboard },
  { path: '/l1', component: L1Seed },
  { path: '/orchestrate', component: Orchestration, meta: { layer: 'l2' } },
  { path: '/l3l4', component: Orchestration, meta: { layer: 'l3l4' } },

  { path: '/worldbook', component: WorldBook },
  { path: '/library', component: Library },
  { path: '/settings', component: Settings },
  { path: '/chat-popup', component: ChatPopup },
  { path: '/l3l4-chat', component: ChatPopup },
  { path: '/output', component: OutputPage },
  { path: '/view', component: ViewerPage },
  { path: '/worldbook-manager', component: WorldBookManager },
  { path: '/rag', component: RAGManager }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const app = createApp(App)
app.use(router)
app.mount('#app')
