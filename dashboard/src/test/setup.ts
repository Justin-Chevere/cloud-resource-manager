import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { setToken } from '../session.ts'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  setToken(null)
})
