import { useState, useEffect } from 'react'

function App() {
  const [apiStatus, setApiStatus] = useState('Connecting...')

  useEffect(() => {
    // The compose.yaml maps port 8000, allowing localhost communication
    fetch('http://localhost:8000/health')
      .then(response => response.json())
      .then(data => {
        if (data.status === 'ok') {
          setApiStatus('Connected: Backend is Healthy')
        } else {
          setApiStatus('Connected: Unexpected Response')
        }
      })
      .catch(error => {
        console.error('Fetch error:', error)
        setApiStatus('Disconnected: Cannot reach API')
      })
  }, [])

  return (
    <div style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Smart Agriculture Dashboard</h1>
      <div style={{ background: '#f5f5f5', padding: '1rem', borderRadius: '8px', display: 'inline-block' }}>
        <p style={{ margin: 0 }}>API Status: <strong>{apiStatus}</strong></p>
      </div>
    </div>
  )
}

export default App