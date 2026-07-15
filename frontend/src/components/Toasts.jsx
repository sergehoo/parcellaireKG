import { createContext, useCallback, useContext, useRef, useState } from 'react'

const ToastContext = createContext(() => {})

export function useToast() {
  return useContext(ToastContext)
}

const STYLES = {
  success: 'bg-emerald-600',
  error: 'bg-rose-600',
  info: 'bg-slate-700',
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const counter = useRef(0)

  const push = useCallback((message, type = 'info') => {
    counter.current += 1
    const id = counter.current
    setToasts((current) => [...current, { id, message, type }])
    setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id))
    }, 5000)
  }, [])

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-[1100] flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`${STYLES[toast.type] || STYLES.info} max-w-sm rounded-lg px-4 py-3 text-sm text-white shadow-lg`}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
