'use client';

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { BrandConfig, validateBrandConfig } from '@/types/brand-config';

interface BrandContextValue {
  config: BrandConfig | null;
  loading: boolean;
  error: Error | null;
}

const BrandContext = createContext<BrandContextValue>({
  config: null,
  loading: false,
  error: null,
});

export function useBrand() {
  return useContext(BrandContext);
}

interface BrandProviderProps {
  children: ReactNode;
}

export function BrandProvider({ children }: BrandProviderProps) {
  const [config, setConfig] = useState<BrandConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  
  // Refs to track dynamically created elements
  const cssRef = React.useRef<HTMLLinkElement | null>(null);
  const faviconRef = React.useRef<HTMLLinkElement | null>(null);

  // Load brand configuration
  useEffect(() => {
    const configUrl = process.env.NEXT_PUBLIC_BRAND_CONFIG_URL;
    
    if (!configUrl) {
      // No brand config URL specified, use default Plexus branding
      return;
    }

    setLoading(true);

    fetch(configUrl)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to fetch brand config: ${response.status} ${response.statusText}`);
        }
        return response.json();
      })
      .then(data => {
        if (!validateBrandConfig(data)) {
          throw new Error('Invalid brand configuration format');
        }
        
        setConfig(data);
        setError(null);
      })
      .catch(err => {
        console.error('[BrandProvider] Failed to load brand config:', err);
        setError(err instanceof Error ? err : new Error(String(err)));
        setConfig(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  // Inject custom CSS when config is loaded
  useEffect(() => {
    if (!config?.styles?.cssPath) {
      return;
    }

    const cssPath = config.styles.cssPath;

    // Create link element for custom styles
    const linkElement = document.createElement('link');
    linkElement.rel = 'stylesheet';
    linkElement.href = cssPath;
    linkElement.id = 'brand-custom-styles';

    // Add to document head
    document.head.appendChild(linkElement);
    cssRef.current = linkElement;

    // Cleanup function to remove the link when component unmounts or config changes
    return () => {
      if (cssRef.current && cssRef.current.parentNode) {
        cssRef.current.parentNode.removeChild(cssRef.current);
        cssRef.current = null;
      }
    };
  }, [config]);

  // Inject custom favicon when config is loaded
  useEffect(() => {
    if (!config?.favicon?.faviconPath) {
      return;
    }

    const faviconPath = config.favicon.faviconPath;

    // Hide existing favicon links instead of removing them (to avoid React conflicts)
    const existingFavicons = document.querySelectorAll('link[rel="icon"], link[rel="shortcut icon"]');
    existingFavicons.forEach(link => {
      (link as HTMLLinkElement).media = 'not all'; // Disable without removing from DOM
    });

    // Create new favicon link
    const faviconLink = document.createElement('link');
    faviconLink.rel = 'icon';
    faviconLink.href = faviconPath;
    faviconLink.id = 'brand-custom-favicon';
    document.head.appendChild(faviconLink);
    faviconRef.current = faviconLink;

    // Cleanup function - only remove our element and restore existing ones
    return () => {
      if (faviconRef.current && faviconRef.current.parentNode) {
        faviconRef.current.parentNode.removeChild(faviconRef.current);
        faviconRef.current = null;
      }
      // Restore existing favicons
      existingFavicons.forEach(link => {
        (link as HTMLLinkElement).media = '';
      });
    };
  }, [config]);

  return (
    <BrandContext.Provider value={{ config, loading, error }}>
      {children}
    </BrandContext.Provider>
  );
}
