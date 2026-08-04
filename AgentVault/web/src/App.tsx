import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Knowledge from './pages/Knowledge'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="knowledge" element={<Knowledge />} />
        <Route path="knowledge/*" element={<Knowledge />} />
      </Route>
    </Routes>
  )
}

export default App
