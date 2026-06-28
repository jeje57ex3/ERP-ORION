import api, { SITE_SLUG } from './client'

export const getProducts = (params = {}) =>
  api.get('/siecle/products/', { params: { site: SITE_SLUG, ...params } })
    .then(r => ({ results: r.data.products ?? [], count: r.data.count ?? 0 }))

export const getProduct = (slug) =>
  api.get(`/siecle/products/${slug}/`, { params: { site: SITE_SLUG } }).then(r => r.data)

export const getCollections = () =>
  api.get('/siecle/collections/', { params: { site: SITE_SLUG } })
    .then(r => ({ results: r.data.collections ?? [] }))
