import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'
import { BrandProvider } from '@shared/brand/BrandProvider'
import { ThemeProvider } from '@shared/theme/ThemeProvider'
import { I18nProvider } from '@shared/i18n/I18nProvider'
import App from './App'
import './styles/lunea.css'
import '@shared/theme/themes.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HelmetProvider>
      <BrowserRouter>
        <BrandProvider forcedBrandKey="lunea">
          <ThemeProvider>
            <I18nProvider>
              <App />
            </I18nProvider>
          </ThemeProvider>
        </BrandProvider>
      </BrowserRouter>
    </HelmetProvider>
  </React.StrictMode>
)
