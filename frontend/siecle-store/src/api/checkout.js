import api, { SITE_SLUG } from './client'

export const validateCart = (items) =>
  api.post('/siecle/cart/validate/', { items }).then(r => r.data)

export const createCheckoutSession = (items, email = '') => {
  const origin = window.location.origin
  return api.post('/siecle/create-checkout-session/', {
    site:        SITE_SLUG,
    items,
    email,
    success_url: `${origin}/checkout/success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url:  `${origin}/checkout/cancel`,
  }).then(r => r.data)
}
