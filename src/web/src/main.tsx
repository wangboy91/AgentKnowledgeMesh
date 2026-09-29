import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider } from './ThemeContext'
import App from './App'
import { BASE_PATH } from './runtime'
import './i18n' // i18n 初始化(默认中文)
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {/* basename 取自服务端注入的部署前缀(subpath-deployment):
        `/`(根路径部署)或 `/akm/`(子路径部署)。 */}
    <BrowserRouter basename={BASE_PATH}>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
