/** i18n 初始化:默认中文,可经 akm.lang 持久化切换 zh/en. */
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import zh from './zh'
import en from './en'

export type Lang = 'zh' | 'en'
const VALID: Record<Lang, 1> = { zh: 1, en: 1 }

function readSaved(): Lang | null {
  try {
    const v = localStorage.getItem('akm.lang') as Lang | null
    return v && v in VALID ? v : null
  } catch {
    return null
  }
}

i18n.use(initReactI18next).init({
  resources: {
    zh: { translation: zh },
    en: { translation: en },
  },
  lng: readSaved() ?? 'zh',
  fallbackLng: 'zh',
  interpolation: { escapeValue: false },
})

/** 切换语言并持久化(localStorage: akm.lang) */
export function setLang(lng: Lang): void {
  i18n.changeLanguage(lng)
  try {
    localStorage.setItem('akm.lang', lng)
  } catch {
    /* 存储不可用时仅当次会话生效 */
  }
}

export function getLang(): Lang {
  return (readSaved() ?? (i18n.resolvedLanguage === 'en' ? 'en' : 'zh'))
}

export default i18n