import React, { createContext, useContext, useState, useEffect } from 'react';
import { getThemeConfig } from './themeConfig';
import { useBrand } from '../brand/BrandProvider';

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const { brandKey, brandConfig } = useBrand();
  const [themeKey, setThemeKeyState] = useState(brandConfig.defaultTheme);

  useEffect(() => {
    // When brand changes, reset to brand default
    setThemeKeyState(brandConfig.defaultTheme);
  }, [brandKey, brandConfig.defaultTheme]);

  useEffect(() => {
    const cfg = getThemeConfig(themeKey);
    // Remove all theme-* classes then apply new one
    document.body.className = document.body.className
      .split(' ')
      .filter(c => !c.startsWith('theme-'))
      .join(' ');
    document.body.classList.add(cfg.bodyClass);
  }, [themeKey]);

  function setTheme(key) {
    setThemeKeyState(key);
    try {
      localStorage.setItem(`theme:${brandKey}`, key);
    } catch {}
  }

  return (
    <ThemeContext.Provider value={{ themeKey, setTheme, themeConfig: getThemeConfig(themeKey) }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider');
  return ctx;
}
