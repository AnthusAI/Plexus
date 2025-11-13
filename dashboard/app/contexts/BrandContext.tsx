'use client';

import React, { createContext, useContext, useEffect, useState, ReactNode, ComponentType } from 'react';
import { BrandConfig, validateBrandConfig } from '@/types/brand-config';
import { LogoVariant } from '@/components/logo-square';

interface LogoComponentProps {
  variant: LogoVariant;
  className?: string;
  shadowEnabled?: boolean;
  shadowWidth?: string;
  shadowIntensity?: number;
}

interface BrandContextValue {
  config: BrandConfig | null;
  loading: boolean;
  error: Error | null;
  customLogoComponent: ComponentType<LogoComponentProps> | null;
  logoLoading: boolean;
  logoError: Error | null;
}

const BrandContext = createContext<BrandContextValue>({
  config: null,
  loading: false,
  error: null,
  customLogoComponent: null,
  logoLoading: false,
  logoError: null,
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
  const [customLogoComponent, setCustomLogoComponent] = useState<ComponentType<LogoComponentProps> | null>(null);
  const [logoLoading, setLogoLoading] = useState(false);
  const [logoError, setLogoError] = useState<Error | null>(null);

  // Load brand configuration
  useEffect(() => {
    const configUrl = process.env.NEXT_PUBLIC_BRAND_CONFIG_URL;
    
    if (!configUrl) {
      // No brand config URL specified, use default Plexus branding
      console.log('[BrandProvider] No NEXT_PUBLIC_BRAND_CONFIG_URL specified, using default branding');
      return;
    }

    console.log('[BrandProvider] Loading brand config from:', configUrl);
    setLoading(true);

    fetch(configUrl)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to fetch brand config: ${response.status} ${response.statusText}`);
        }
        return response.json();
      })
      .then(data => {
        console.log('[BrandProvider] Fetched brand config:', data);
        
        if (!validateBrandConfig(data)) {
          throw new Error('Invalid brand configuration format');
        }
        
        console.log('[BrandProvider] Brand config validated successfully');
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
    console.log('[BrandProvider] Injecting custom CSS from:', cssPath);

    // Create link element for custom styles
    const linkElement = document.createElement('link');
    linkElement.rel = 'stylesheet';
    linkElement.href = cssPath;
    linkElement.id = 'brand-custom-styles';

    // Add to document head
    document.head.appendChild(linkElement);

    // Cleanup function to remove the link when component unmounts or config changes
    return () => {
      const existingLink = document.getElementById('brand-custom-styles');
      if (existingLink) {
        existingLink.remove();
      }
    };
  }, [config]);

  // Load custom logo component when config is loaded
  useEffect(() => {
    if (!config?.logo?.componentPath) {
      return;
    }

    const componentPath = config.logo.componentPath;
    console.log('[BrandProvider] Loading custom logo component from:', componentPath);
    setLogoLoading(true);

    // Load the ES module by creating a script tag with type="module"
    const scriptId = 'brand-custom-logo';
    const existingScript = document.getElementById(scriptId);
    if (existingScript) {
      existingScript.remove();
    }

    const script = document.createElement('script');
    script.id = scriptId;
    script.type = 'module';
    script.textContent = `
      import CustomLogo from '${componentPath}';
      window.__BRAND_CUSTOM_LOGO__ = CustomLogo;
      window.dispatchEvent(new CustomEvent('brand-logo-loaded'));
    `;

    const handleLogoLoaded = () => {
      const CustomLogo = (window as any).__BRAND_CUSTOM_LOGO__;
      if (CustomLogo) {
        console.log('[BrandProvider] Custom logo component loaded successfully');
        setCustomLogoComponent(() => CustomLogo);
        setLogoError(null);
      } else {
        throw new Error('Custom logo component not found on window object');
      }
      setLogoLoading(false);
    };

    const handleError = (err: any) => {
      console.error('[BrandProvider] Failed to load custom logo component:', err);
      setLogoError(err instanceof Error ? err : new Error(String(err)));
      setCustomLogoComponent(null);
      setLogoLoading(false);
    };

    window.addEventListener('brand-logo-loaded', handleLogoLoaded);
    script.onerror = handleError;

    document.head.appendChild(script);

    // Cleanup
    return () => {
      window.removeEventListener('brand-logo-loaded', handleLogoLoaded);
      const scriptToRemove = document.getElementById(scriptId);
      if (scriptToRemove) {
        scriptToRemove.remove();
      }
      delete (window as any).__BRAND_CUSTOM_LOGO__;
    };
  }, [config]);

  return (
    <BrandContext.Provider value={{ config, loading, error, customLogoComponent, logoLoading, logoError }}>
      {children}
    </BrandContext.Provider>
  );
}

