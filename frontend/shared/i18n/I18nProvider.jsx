import React, { createContext, useContext, useState } from 'react';
import { TRANSLATIONS } from './translations';
import { useBrand } from '../brand/BrandProvider';

const I18nContext = createContext(null);

export function I18nProvider({ children }) {
  const { brandConfig } = useBrand();
  const [lang, setLang] = useState(brandConfig.defaultLanguage);

  function t(key) {
    return (TRANSLATIONS[lang] || TRANSLATIONS.fr)[key] || key;
  }

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used inside I18nProvider');
  return ctx;
}
