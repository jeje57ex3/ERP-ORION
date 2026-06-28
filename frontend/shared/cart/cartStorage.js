import { getBrandConfig } from '../brand/brandConfig';

function storageKey(brandKey) {
  return getBrandConfig(brandKey).cartStorageKey;
}

function wishlistKey(brandKey) {
  return getBrandConfig(brandKey).wishlistStorageKey;
}

// ── Cart ─────────────────────────────────────────────────────────────────────

export function getCart(brandKey) {
  try {
    return JSON.parse(localStorage.getItem(storageKey(brandKey)) || 'null') || { items: [], brand_key: brandKey };
  } catch {
    return { items: [], brand_key: brandKey };
  }
}

export function saveCart(brandKey, cart) {
  localStorage.setItem(storageKey(brandKey), JSON.stringify({ ...cart, brand_key: brandKey }));
}

export function clearCart(brandKey) {
  localStorage.removeItem(storageKey(brandKey));
}

export function addToCart(brandKey, product, quantity = 1) {
  const cart = getCart(brandKey);
  const existing = cart.items.find(i => i.product_id === product.id);
  if (existing) {
    existing.quantity += quantity;
  } else {
    cart.items.push({
      product_id: product.id,
      product_name: product.name,
      unit_price: product.price,
      quantity,
    });
  }
  saveCart(brandKey, cart);
  return cart;
}

export function removeFromCart(brandKey, productId) {
  const cart = getCart(brandKey);
  cart.items = cart.items.filter(i => i.product_id !== productId);
  saveCart(brandKey, cart);
  return cart;
}

export function getCartCount(brandKey) {
  return getCart(brandKey).items.reduce((sum, i) => sum + i.quantity, 0);
}

// ── Wishlist ─────────────────────────────────────────────────────────────────

export function getWishlist(brandKey) {
  try {
    return JSON.parse(localStorage.getItem(wishlistKey(brandKey)) || '[]');
  } catch {
    return [];
  }
}

export function toggleWishlist(brandKey, product) {
  const list = getWishlist(brandKey);
  const idx = list.findIndex(i => i.product_id === product.id);
  if (idx === -1) {
    list.push({ product_id: product.id, product_name: product.name });
  } else {
    list.splice(idx, 1);
  }
  localStorage.setItem(wishlistKey(brandKey), JSON.stringify(list));
  return list;
}

export function isInWishlist(brandKey, productId) {
  return getWishlist(brandKey).some(i => i.product_id === productId);
}
