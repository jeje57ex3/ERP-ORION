import MakeupTopBar from '../components/makeup/MakeupTopBar'
import MakeupHeader from '../components/makeup/MakeupHeader'
import MakeupFooter from '../components/makeup/MakeupFooter'
import CartSidebar  from '../components/CartSidebar'
import '../styles/makeup-home.css'

export default function MakeupLayout({ children }) {
  return (
    <div className="makeup-site">
      <CartSidebar />
      <MakeupTopBar />
      <MakeupHeader />
      <main className="makeup-main">
        {children}
      </main>
      <MakeupFooter />
    </div>
  )
}
