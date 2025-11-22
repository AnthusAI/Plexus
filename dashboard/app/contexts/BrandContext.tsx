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

  // Load custom logo component when config is loaded
  useEffect(() => {
    if (!config?.logo?.componentPath) {
      return;
    }

    const componentPath = config.logo.componentPath;
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

