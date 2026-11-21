import { type Dispatch, type SetStateAction, useEffect, useState } from 'react'

/**
 * State kept in this browser only (coach edits, series plans): per user, never shared. Storage can be missing or
 * blocked (private mode), so reads and writes fall back to memory.
 */
export function useLocalState<T>(key: string, initial: T): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw === null ? initial : (JSON.parse(raw) as T)
    } catch {
      return initial
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value))
    } catch {
      // storage unavailable: the value still lives for this session
    }
  }, [key, value])
  useEffect(() => {
    // another tab changed it: take its value instead of overwriting it with ours on the next edit
    const onStorage = (e: StorageEvent) => {
      if (e.key === key) {
        try {
          setValue(e.newValue === null ? initial : (JSON.parse(e.newValue) as T))
        } catch {
          // unreadable value from another tab: keep ours
        }
      }
    }
    globalThis.addEventListener('storage', onStorage)
    return () => globalThis.removeEventListener('storage', onStorage)
  }, [key, initial])
  return [value, setValue]
}

/** A random id; crypto.randomUUID needs a secure context (HTTPS or localhost). */
export function newId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

export function download(name: string, text: string, type: string): void {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}
