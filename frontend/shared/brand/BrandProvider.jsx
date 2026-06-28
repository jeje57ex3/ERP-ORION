import React, { createContext, useContext, useState, useEffect } from 'react';
import { getBrandConfig, SUPPORTED_BRANDS } from './brandConfig';

const BrandContext = createContext(null);

function detectBrandKey(forcedBrandKey) {
  if (forcedBrandKey && SUPPORTED_BRANDS.includes(forcedBrandKey)) {
    return forcedBrandKey;
  }
  const host = window.location.hostname.toLowerCase();
  const path = window.location.pathname.toLowerCase();
  if (host.includes('lunea') || path.startsWith('/lunea') || path.startsWith('/api/v1/lunea')) {
    return 'lunea';
  }
  if (host.includes('siecle') || path.startsWith('/siecle') || path.startsWith('/api/v1/siecle')) {
    return 'siecle';
  }
  return 'siecle';
}

export function BrandProvider({ children, forcedBrandKey = null }) {
  const [brandKey, setBrandKey] = useState(() => detectBrandKey(forcedBrandKey));
  const brandConfig = getBrandConfig(brandKey);

  useEffect(() => {
    document.documentElement.setAttribute('data-brand', brandKey);
    document.title = brandConfig.displayName;
    const favicon = document.querySelector("link[rel~='icon']");
    if (favicon) favicon.href = brandConfig.favicon;
  }, [brandKey, brandConfig]);

  return (
    <BrandContext.Provider value={{ brandKey, brandConfig, setBrandKey }}>
      {children}
    </BrandContext.Provider>
  );
}

export function useBrand() {
  const ctx = useContext(BrandContext);
  if (!ctx) throw new Error('useBrand must be used inside BrandProvider');
  return ctx;
}
