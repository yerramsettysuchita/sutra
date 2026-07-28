/**
 * Interface language, held in one place and remembered between visits.
 *
 * The choice goes to localStorage rather than a route or a query parameter,
 * because an officer picks a language once and should never pick it again. It
 * also goes onto the document element as `lang` and `data-lang`, so the font
 * stack, the line height and any assistive technology all follow from one
 * attribute rather than from component state.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { translate, type Language } from './strings'

const KEY = 'sutra.language'

function initial(): Language {
  try {
    return window.localStorage.getItem(KEY) === 'kn' ? 'kn' : 'en'
  } catch {
    // Private browsing and some kiosk builds throw on access rather than
    // returning null. English is the safe default and the toggle still works
    // for the session.
    return 'en'
  }
}

type Ctx = {
  language: Language
  setLanguage: (next: Language) => void
  t: (text: string) => string
}

const LanguageContext = createContext<Ctx>({
  language: 'en',
  setLanguage: () => {},
  t: (text) => text,
})

export function LanguageProvider({
  children,
  defaultLanguage,
}: {
  children: ReactNode
  /** Forces the starting language, ignoring storage. Only the smoke render
   *  uses it, so that both languages can be rendered in one process where
   *  there is no localStorage to set. */
  defaultLanguage?: Language
}) {
  const [language, setLanguageState] = useState<Language>(
    () => defaultLanguage ?? initial(),
  )

  useEffect(() => {
    const root = document.documentElement
    root.setAttribute('lang', language)
    root.setAttribute('data-lang', language)
  }, [language])

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(next)
    try {
      window.localStorage.setItem(KEY, next)
    } catch {
      /* the session still switches, it just will not be remembered */
    }
  }, [])

  const value = useMemo<Ctx>(
    () => ({
      language,
      setLanguage,
      t: (text: string) => translate(text, language),
    }),
    [language, setLanguage],
  )

  return (
    <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
  )
}

export function useLanguage(): Ctx {
  return useContext(LanguageContext)
}

/** The common case, translating a single chrome string. */
export function useT(): (text: string) => string {
  return useContext(LanguageContext).t
}
