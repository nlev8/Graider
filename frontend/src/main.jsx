import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import ErrorBoundary from './components/ErrorBoundary'
import { installStaleChunkRecovery } from './staleChunkRecovery'
import './styles/globals.css'

// Auto-recover a tab left open across a deploy: a missing lazy chunk now 404s
// (backend handle_404) → Vite fires vite:preloadError → reload once.
installStaleChunkRecovery()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
