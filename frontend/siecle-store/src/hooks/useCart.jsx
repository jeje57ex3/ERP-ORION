import { createContext, useContext, useState, useEffect } from 'react'

const CartContext = createContext(null)

// Cart item key — custom watches get a unique key per configuration
function itemKey(item) {
  if (item.isCustomWatch) return item.id  // already unique (includes config hash)
  return `${item.id}__${item.size || ''}`
}

export function CartProvider({ children }) {
  const [items, setItems] = useState(() => {
    try { return JSON.parse(localStorage.getItem('siecle_cart') || '[]') }
    catch { return [] }
  })
  const [isOpen, setIsOpen] = useState(false)
  const [toast,  setToast]  = useState(null)

  const showToast = (product) => {
    const price  = parseFloat(product.final_price ?? product.price ?? 0)
    const points = Math.floor(price)
    setToast({ id: Date.now(), name: product.name, points })
    setTimeout(() => setToast(null), 3200)
  }

  useEffect(() => {
    localStorage.setItem('siecle_cart', JSON.stringify(items))
  }, [items])

  const addItem = (product, size = '') => {
    showToast(product)
    setItems(prev => {
      const key = itemKey({ ...product, size })

      // Custom watches: always a new line unless exact same config key exists
      if (product.isCustomWatch) {
        const existing = prev.find(i => itemKey(i) === key)
        if (existing) {
          return prev.map(i => itemKey(i) === key ? { ...i, qty: i.qty + 1 } : i)
        }
        return [...prev, {
          ...product,
          size: size || '',
          qty: 1,
          // Ensure price reflects final_price for display
          price: String(product.final_price ?? product.price),
        }]
      }

      // Standard item
      const existing = prev.find(i => itemKey(i) === key)
      if (existing) {
        return prev.map(i => itemKey(i) === key ? { ...i, qty: i.qty + 1 } : i)
      }
      const img = product.image || product.gallery?.[0] || null
      return [...prev, {
        id: product.id, slug: product.slug, name: product.name,
        price: product.price, size, qty: 1, image: img,
      }]
    })
  }

  // addToCart is an alias kept for components that use it
  const addToCart = (product, qty = 1) => {
    for (let i = 0; i < qty; i++) addItem(product, '')
  }

  const removeItem = (id, size = '') => {
    setItems(prev => prev.filter(i => {
      if (i.isCustomWatch) return i.id !== id
      return !(i.id === id && (i.size || '') === (size || ''))
    }))
  }

  const updateQty = (id, size, qty) => {
    if (qty < 1) { removeItem(id, size); return }
    setItems(prev => prev.map(i => {
      if (i.isCustomWatch) return i.id === id ? { ...i, qty } : i
      return i.id === id && (i.size || '') === (size || '') ? { ...i, qty } : i
    }))
  }

  const clearCart = () => setItems([])

  const total      = items.reduce((sum, i) => sum + parseFloat(i.price || 0) * i.qty, 0)
  const count      = items.reduce((sum, i) => sum + i.qty, 0)
  const totalItems = count  // alias used by MakeupHeader

  return (
    <CartContext.Provider value={{
      items, addItem, addToCart, removeItem, updateQty, clearCart,
      total, count, totalItems,
      isOpen, setIsOpen,
      toast,
    }}>
      {children}
    </CartContext.Provider>
  )
}

export function useCart() {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart must be used within CartProvider')
  return ctx
}
