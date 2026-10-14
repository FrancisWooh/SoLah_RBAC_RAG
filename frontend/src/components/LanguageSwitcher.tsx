import { Button } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import { useLanguage } from '../i18n/LanguageProvider'

export default function LanguageSwitcher() {
  const { lang, toggleLang } = useLanguage()
  return (
    <Button
      size="small"
      type="text"
      icon={<GlobalOutlined />}
      onClick={toggleLang}
    >
      {lang === 'zh' ? 'English' : '中文'}
    </Button>
  )
}
