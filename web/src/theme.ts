/** Light / dark mode: follows the system until the user picks one, then remembers it (per browser). */
export type Theme = 'light' | 'dark'

const KEY = 'fele-theme'

function storedTheme(): Theme | null {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

export function initialTheme(): Theme {
  return storedTheme() ?? (globalThis.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
}

export function applyTheme(theme: Theme, remember = false): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  if (remember) {
    try {
      localStorage.setItem(KEY, theme)
    } catch {
      // private mode / blocked storage: the choice just isn't remembered
    }
  }
}
