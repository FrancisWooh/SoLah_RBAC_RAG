import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import './i18n'
import { LanguageProvider } from './i18n/LanguageProvider'
import App from './App.tsx'
import AdminApp from './AdminApp.tsx'

// `vite --mode admin` (port 5174) serves the management console on its own
const Root = import.meta.env.MODE === 'admin' ? AdminApp : App

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <LanguageProvider>
        <Root />
      </LanguageProvider>
    </BrowserRouter>
  </StrictMode>,
)
