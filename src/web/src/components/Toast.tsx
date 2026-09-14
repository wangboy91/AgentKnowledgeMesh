/**
 * 轻量级 Toast 系统
 * - useToast() 暴露 success / info / warning / danger
 * - mount 点是 <ToastHost />,挂在 App 根
 * - 与 i18n 集成:可传 i18n key
 */
import { createContext, useCallback, useContext, useState, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { XIcon, CheckIcon, AlertIcon } from './Icon'

export type ToastVariant = 'success' | 'info' | 'warning' | 'danger'

interface ToastInput {
  message: string
  variant?: ToastVariant
  duration?: number
}

interface Toast extends ToastInput {
  id: number
  variant: ToastVariant
}

interface ToastCtx {
  show(input: ToastInput | string): void
  success(message: string): void
  info(message: string): void
  warning(message: string): void
  danger(message: string): void
}

const Ctx = createContext<ToastCtx | null>(null)

let counter = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const show = useCallback(
    (input: ToastInput | string) => {
      const opts: ToastInput = typeof input === 'string' ? { message: input } : input
      const id = ++counter
      const variant = opts.variant ?? 'info'
      const duration = opts.duration ?? (variant === 'danger' ? 6000 : 3500)
      setToasts((prev) => [...prev, { ...opts, variant, id }])
      window.setTimeout(() => dismiss(id), duration)
    },
    [dismiss]
  )

  const value: ToastCtx = {
    show,
    success: (m) => show({ message: m, variant: 'success' }),
    info: (m) => show({ message: m, variant: 'info' }),
    warning: (m) => show({ message: m, variant: 'warning' }),
    danger: (m) => show({ message: m, variant: 'danger' }),
  }

  return (
    <Ctx.Provider value={value}>
      {children}
      <ToastHost toasts={toasts} onDismiss={dismiss} />
    </Ctx.Provider>
  )
}

function ToastHost({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div className="toast-host" aria-live="polite" aria-atomic="true">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={() => onDismiss(t.id)} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const { t } = useTranslation()
  const cls = ['toast', `toast--${toast.variant}`]
  return (
    <div className={cls.join(' ')}>
      <span className="toast__icon">
        {toast.variant === 'success' ? <CheckIcon /> : <AlertIcon />}
      </span>
      <div className="toast__body">{toast.message}</div>
      <button
        className="toast__close"
        onClick={onDismiss}
        aria-label={t('common.close')}
      >
        <XIcon size={14} />
      </button>
    </div>
  )
}

export function useToast(): ToastCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}

/**
 * 把 fetch 错误转成 toast.danger
 * 使用方只需 import 后调用 reportError(err)
 */
export function useErrorReporter() {
  const toast = useToast()
  const { t } = useTranslation()
  return useCallback(
    (err: unknown) => {
      const msg =
        err instanceof Error
          ? err.message
          : t('auth.httpError')
      toast.danger(msg)
    },
    [toast, t]
  )
}
