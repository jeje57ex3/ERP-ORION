import { BrandProvider } from '@shared/brand/BrandProvider'
import { ThemeProvider } from '@shared/theme/ThemeProvider'
import { ForgotPasswordPage } from '@shared/auth/ForgotPasswordPage'
import '@shared/theme/themes.css'

export default function LuneaForgotPassword() {
  return (
    <BrandProvider forcedBrandKey="lunea">
      <ThemeProvider>
        <ForgotPasswordPage />
      </ThemeProvider>
    </BrandProvider>
  )
}
