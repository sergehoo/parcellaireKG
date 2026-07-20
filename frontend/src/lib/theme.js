// Thème clair/sombre : persistant (localStorage) + repli sur la préférence
// système. La classe `dark` sur <html> active les surcharges CSS (index.css)
// et les variantes Tailwind `dark:`.
const KEY = 'kg-theme'

export function getTheme() {
  const saved = localStorage.getItem(KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark' : 'light'
}

export function applyTheme(theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

export function setTheme(theme) {
  localStorage.setItem(KEY, theme)
  applyTheme(theme)
}

export function initTheme() {
  applyTheme(getTheme())
}
