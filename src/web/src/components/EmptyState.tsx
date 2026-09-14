/**
 * 统一空 / 加载 / 错误 占位组件
 *
 * - icon: 必传 Icon 组件(SunIcon / EmptyDocIcon / AlertIcon / RefreshIcon / FileTree 空态等)
 * - title / desc / actions 是可选的引导文案与操作按钮
 * - 没 actions 也能渲染(纯展示型)
 */
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

interface Props {
  icon: ReactNode
  title: string
  desc?: string
  actions?: ReactNode
  variant?: 'default' | 'danger' | 'scrollable'
}

export default function EmptyState({ icon, title, desc, actions, variant = 'default' }: Props) {
  const { t } = useTranslation()
  const cls = ['state']
  if (variant === 'scrollable') cls.push('state--scrollable')
  const illCls = ['state__illustration']
  if (variant === 'danger') illCls.push('state__illustration--danger')
  return (
    <div className={cls.join(' ')} role="status" aria-live="polite">
      <div className={illCls.join(' ')}>{icon}</div>
      <div className="state__title">{title}</div>
      {desc && <div className="state__desc">{desc}</div>}
      {actions && <div className="state__actions">{actions}</div>}
      {!actions && <span className="sr-only">{t('common.loading')}</span>}
    </div>
  )
}
