import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Knowledge from './pages/Knowledge'
import Nodes from './pages/Nodes'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="knowledge" element={<Knowledge />} />
        <Route path="knowledge/*" element={<Knowledge />} />
        <Route path="nodes" element={<Nodes />} />
      </Route>
    </Routes>
  )
}

export default App
