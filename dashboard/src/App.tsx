import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Dashboard } from './Dashboard.tsx'
import { LoginPage } from './LoginPage.tsx'
import { useToken } from './session.ts'

export default function App() {
  const token = useToken()
  const queryClient = useQueryClient()

  useEffect(() => {
    // Forget every cached response on sign-out, so whoever signs in next never
    // sees the previous user's data, not even for a moment.
    if (!token) queryClient.clear()
  }, [token, queryClient])

  return token ? <Dashboard /> : <LoginPage />
}
