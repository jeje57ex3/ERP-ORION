import { useState, useEffect, useCallback } from 'react'
import { getToken, portalFetchMe, portalLogin, portalLogout } from '../api/portal'

export function useClientAuth() {
  const [account, setAccount] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) { setLoading(false); return }
    portalFetchMe()
      .then(setAccount)
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email, password) => {
    const acc = await portalLogin(email, password)
    setAccount(acc)
    return acc
  }, [])

  const logout = useCallback(async () => {
    await portalLogout()
    setAccount(null)
  }, [])

  return { account, loading, isAuthenticated: !!account, login, logout }
}
