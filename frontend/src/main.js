import { createApp } from 'vue'
import '@fontsource-variable/geist'
import './motion.css'
import './style.css'
import './floating-navigation.css'
import App from './App.vue'
import { installIconMotion } from './icon-motion.js'

createApp(App).mount('#app')

const iconMotion = installIconMotion(document)
if (import.meta.hot) import.meta.hot.dispose(() => iconMotion.destroy())
