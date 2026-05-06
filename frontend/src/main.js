import Vue from 'vue'
import App from './App.vue'
import router from './router'
import store from './store'
import ElementUI from 'element-ui'
import 'element-ui/lib/theme-chalk/index.css'
import './styles/font-size.css'
import axios from 'axios'

// 配置 axios
axios.defaults.baseURL = process.env.VUE_APP_API_BASE_URL || ''
axios.defaults.withCredentials = true
Vue.prototype.$axios = axios

Vue.use(ElementUI)
Vue.config.productionTip = false

// 初始化主题（在 Vue 实例创建之前）
const savedTheme = localStorage.getItem('lawyerclaw-theme')
if (savedTheme === 'dark') {
  document.documentElement.setAttribute('data-theme', 'dark')
}

new Vue({
  router,
  store,
  render: h => h(App)
}).$mount('#app')
