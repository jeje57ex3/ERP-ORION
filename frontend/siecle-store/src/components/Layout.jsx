import { Outlet } from 'react-router-dom'
import Header from './Header'
import Footer from './Footer'
import CartSidebar from './CartSidebar'

export default function Layout() {
  return (
    <>
      <Header />
      <CartSidebar />
      <main>
        <Outlet />
      </main>
      <Footer />
    </>
  )
}
