import axios from 'axios'

const SITE_SLUG = 'siecle'

const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json', 'X-Site-Slug': SITE_SLUG },
})

export { SITE_SLUG }
export default api
