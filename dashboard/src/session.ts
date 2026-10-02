import { useSyncExternalStore } from 'react'

// The sign-in token lives in sessionStorage: it survives a page reload but not
// closing the tab, and other tabs can't see it. (An HttpOnly cookie would keep it
// out of reach of page scripts entirely, at the cost of server-side changes.)
const KEY = 'crm.token'
const listeners = new Set<() => void>()
let token = readStoredToken()

function readStoredToken(): string | null {
  try {
    return sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function getToken(): string | null {
  return token
}

export function setToken(next: string | null): void {
  token = next
  try {
    if (next) sessionStorage.setItem(KEY, next)
    else sessionStorage.removeItem(KEY)
  } catch {
    // Storage can be blocked (private windows, site settings); memory still works.
  }
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

// Re-renders the caller whenever someone signs in or out.
export function useToken(): string | null {
  return useSyncExternalStore(subscribe, getToken)
}
