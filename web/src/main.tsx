import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import './styles/fonts.css'
import './styles/tokens.css'
import './styles/base.css'
import './styles/primitives.css'
import './styles/screen.css'
import './styles/app.css'
import './styles/hero.css'
import './styles/print.css'

import App from './App'
import { LanguageProvider } from './i18n/useLanguage'
import { DecisionProvider } from './decisions/useDecisions'

const root = document.getElementById('root')
if (!root) throw new Error('#root not found')

createRoot(root).render(
  <StrictMode>
    {/* Above the router, because the language survives navigation and the
        loading and error states are chrome too. */}
    <LanguageProvider>
      {/* Above the router, because a decision taken on the review queue has to
          be visible on the audit trail without either screen owning the log. */}
      <DecisionProvider>
        <App />
      </DecisionProvider>
    </LanguageProvider>
  </StrictMode>,
)
