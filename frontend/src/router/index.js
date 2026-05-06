import Vue from 'vue'
import VueRouter from 'vue-router'
import ChatView from '../views/Chat.vue'
import ToolsView from '../views/Tools.vue'
import SettingsView from '../views/Settings.vue'

Vue.use(VueRouter)

const routes = [
  { path: '/', redirect: '/chat' },
  { path: '/chat', component: ChatView },
  { path: '/tools', component: ToolsView },
  { path: '/settings', component: SettingsView }
]

const router = new VueRouter({
  mode: 'history',
  base: '/',
  routes
})

export default router
