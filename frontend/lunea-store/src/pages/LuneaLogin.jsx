import { BrandProvider } from '@shared/brand/BrandProvider'
import { ThemeProvider } from '@shared/theme/ThemeProvider'
import { LoginPage } from '@shared/auth/LoginPage'
import '@shared/theme/themes.css'

export default function LuneaLogin() {
  return (
    <BrandProvider forcedBrandKey="lunea">
      <ThemeProvider>
        <LoginPage />
      </ThemeProvider>
    </BrandProvider>
  )
}
