<template>
  <div id="app" :style="appStyle">
    <nav class="navbar">
      <div class="nav-left">
        <div class="nav-brand">AI网文创作系统</div>
        <div class="nav-title" v-if="$route.path !== '/'">{{ pageTitle }}</div>
        <div class="nav-layers">
          <router-link to="/">仪表盘</router-link>
          <router-link to="/l1">L1</router-link>
          <router-link to="/l2">L2</router-link>
          <router-link to="/l3">L3</router-link>
          <router-link to="/l4">L4</router-link>
          <router-link to="/settings">设置</router-link>
        </div>
      </div>
      <div class="nav-controls">
        <button class="btn-icon" @click="zoomOut">−</button>
        <span class="zoom-level">{{ Math.round(scale * 100) }}%</span>
        <button class="btn-icon" @click="zoomIn">+</button>
        <button class="btn-icon" @click="resetZoom">⟲</button>
      </div>
    </nav>
    <main class="main-content">
      <router-view></router-view>
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const scale = ref(1)

const pageTitle = computed(() => {
  const titles = {
    '/l1': 'L1 种子层',
    '/l2': 'L2 架构层',
    '/l3': 'L3 叙事层',
    '/l4': 'L4 渲染层',
    '/settings': '系统设置'
  }
  return titles[route.path] || ''
})

const zoomIn = () => { scale.value = Math.min(scale.value + 0.1, 1.5) }
const zoomOut = () => { scale.value = Math.max(scale.value - 0.1, 0.7) }
const resetZoom = () => { scale.value = 1 }

const appStyle = computed(() => ({
  transform: `scale(${scale.value})`,
  transformOrigin: 'top left',
  width: `${100 / scale.value}%`,
  height: `${100 / scale.value}%`,
  position: 'absolute',
  top: 0,
  left: 0
}))
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: #f5f5f5;
}

html, body {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

#app {
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.navbar {
  background-color: #2c3e50;
  color: white;
  padding: 0.5rem 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 42px;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 2rem;
}

.nav-brand {
  font-size: 1rem;
  font-weight: bold;
}

.nav-title {
  font-size: 0.875rem;
  color: #3498db;
  padding: 0.25rem 0.75rem;
  background: rgba(52, 152, 219, 0.1);
  border-radius: 4px;
}

.nav-layers {
  display: flex;
  gap: 0.5rem;
}

.nav-layers a {
  color: white;
  text-decoration: none;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.875rem;
  opacity: 0.8;
}

.nav-layers a:hover {
  opacity: 1;
  background: rgba(255,255,255,0.1);
}

.nav-layers a.router-link-active {
  opacity: 1;
  background: #3498db;
}

.nav-controls {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.btn-icon {
  width: 28px;
  height: 28px;
  border: none;
  background: rgba(255,255,255,0.1);
  color: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover {
  background: rgba(255,255,255,0.2);
}

.zoom-level {
  font-size: 0.75rem;
  color: white;
  min-width: 3rem;
  text-align: center;
}

.btn-icon {
  width: 28px;
  height: 28px;
  border: none;
  background: rgba(255,255,255,0.1);
  color: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover {
  background: rgba(255,255,255,0.2);
}

.zoom-level {
  font-size: 0.75rem;
  color: white;
  min-width: 3rem;
  text-align: center;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
  margin: 0;
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.btn-primary {
  background-color: #3498db;
  color: white;
}

.btn-primary:hover {
  background-color: #2980b9;
}

.btn-success {
  background-color: #27ae60;
  color: white;
}

.btn-danger {
  background-color: #e74c3c;
  color: white;
}

.card {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  margin-bottom: 1rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.form-group input,
.form-group textarea,
.form-group select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

.form-group textarea {
  min-height: 100px;
  resize: vertical;
}
</style>
