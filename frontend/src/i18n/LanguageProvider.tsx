import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import enUS from 'antd/locale/en_US'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import 'dayjs/locale/en'
import { useTranslation } from 'react-i18next'

type Lang = 'zh' | 'en'

interface LanguageContextValue {
  lang: Lang
  setLang: (lang: Lang) => void
  toggleLang: () => void
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const { i18n } = useTranslation()
  const [lang, setLangState] = useState<Lang>(
    () => (localStorage.getItem('lang') as Lang) || 'en',
  )

  const setLang = (next: Lang) => {
    setLangState(next)
    localStorage.setItem('lang', next)
    i18n.changeLanguage(next)
    dayjs.locale(next === 'zh' ? 'zh-cn' : 'en')
  }

  const toggleLang = () => setLang(lang === 'zh' ? 'en' : 'zh')

  useEffect(() => {
    dayjs.locale(lang === 'zh' ? 'zh-cn' : 'en')
    i18n.changeLanguage(lang)
  }, [])

  return (
    <LanguageContext.Provider value={{ lang, setLang, toggleLang }}>
      <ConfigProvider locale={lang === 'zh' ? zhCN : enUS}>
        {children}
      </ConfigProvider>
    </LanguageContext.Provider>
  )
}

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider')
  return ctx
}
