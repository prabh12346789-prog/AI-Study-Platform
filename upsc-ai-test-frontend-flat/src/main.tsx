import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import './premium-final.css'
import './chat-final.css'
import './phase-four.css'
import './dashboard-reference.css'
import './phase-two.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
