import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'
import { BrandProvider } from '../../shared/brand/BrandProvider'
import { ThemeProvider } from '../../shared/theme/ThemeProvider'
import App from './App'
import './styles/globals.css'
import './styles/siecle.css'
import './styles/powered-by-orion.css'
import '../../shared/theme/themes.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HelmetProvider>
      <BrowserRouter>
        <BrandProvider forcedBrandKey="siecle">
          <ThemeProvider>
            <App />
          </ThemeProvider>
        </BrandProvider>
      </BrowserRouter>
    </HelmetProvider>
  </React.StrictMode>
)
