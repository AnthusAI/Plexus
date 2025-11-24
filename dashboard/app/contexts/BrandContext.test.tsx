import React from 'react';
import { render, waitFor, screen } from '@testing-library/react';
import { BrandProvider, useBrand } from './BrandContext';

// Mock fetch
global.fetch = jest.fn();

// Test component that uses the brand context
function TestComponent() {
  const { config, loading, error } = useBrand();
  
  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;
  if (config) return <div>Brand: {config.name}</div>;
  return <div>No brand</div>;
}

describe('BrandContext', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Clear any existing brand elements
    document.querySelectorAll('#brand-custom-styles, #brand-custom-favicon').forEach(el => el.remove());
  });

  afterEach(() => {
    // Clean up any remaining brand elements
    document.querySelectorAll('#brand-custom-styles, #brand-custom-favicon').forEach(el => el.remove());
  });

  it('should render without brand config when env var is not set', () => {
    delete process.env.NEXT_PUBLIC_BRAND_CONFIG_URL;
    
    render(
      <BrandProvider>
        <TestComponent />
      </BrandProvider>
    );
    
    expect(screen.getByText('No brand')).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('should load brand config when env var is set', async () => {
    const mockConfig = {
      name: 'Test Brand',
      logo: { componentPath: '/test/logo.js' },
      styles: { cssPath: '/test/styles.css' },
      favicon: { faviconPath: '/test/favicon.ico' }
    };

    process.env.NEXT_PUBLIC_BRAND_CONFIG_URL = '/brands/test/brand.json';
    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfig
    });

    render(
      <BrandProvider>
        <TestComponent />
      </BrandProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Brand: Test Brand')).toBeInTheDocument();
    });

    expect(fetch).toHaveBeenCalledWith('/brands/test/brand.json');
  });

  it('should inject custom CSS link element with ref tracking', async () => {
    const mockConfig = {
      name: 'Test Brand',
      styles: { cssPath: '/test/styles.css' }
    };

    process.env.NEXT_PUBLIC_BRAND_CONFIG_URL = '/brands/test/brand.json';
    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfig
    });

    const { unmount } = render(
      <BrandProvider>
        <TestComponent />
      </BrandProvider>
    );

    await waitFor(() => {
      const cssLink = document.getElementById('brand-custom-styles') as HTMLLinkElement;
      expect(cssLink).toBeInTheDocument();
      expect(cssLink?.href).toContain('/test/styles.css');
      expect(cssLink?.rel).toBe('stylesheet');
    });

    // Verify cleanup removes the element
    unmount();
    await waitFor(() => {
      expect(document.getElementById('brand-custom-styles')).not.toBeInTheDocument();
    });
  });

  it('should inject custom favicon with ref tracking and hide existing favicons', async () => {
    // Add an existing favicon to the document
    const existingFavicon = document.createElement('link');
    existingFavicon.rel = 'icon';
    existingFavicon.href = '/existing-favicon.ico';
    existingFavicon.id = 'existing-favicon';
    document.head.appendChild(existingFavicon);

    const mockConfig = {
      name: 'Test Brand',
      favicon: { faviconPath: '/test/favicon.ico' }
    };

    process.env.NEXT_PUBLIC_BRAND_CONFIG_URL = '/brands/test/brand.json';
    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfig
    });

    const { unmount } = render(
      <BrandProvider>
        <TestComponent />
      </BrandProvider>
    );

    await waitFor(() => {
      const customFavicon = document.getElementById('brand-custom-favicon') as HTMLLinkElement;
      expect(customFavicon).toBeInTheDocument();
      expect(customFavicon?.href).toContain('/test/favicon.ico');
      expect(customFavicon?.rel).toBe('icon');
      
      // Existing favicon should be hidden, not removed
      const existing = document.getElementById('existing-favicon') as HTMLLinkElement;
      expect(existing).toBeInTheDocument();
      expect(existing?.media).toBe('not all');
    });

    // Verify cleanup removes custom favicon and restores existing one
    unmount();
    await waitFor(() => {
      expect(document.getElementById('brand-custom-favicon')).not.toBeInTheDocument();
      
      // Existing favicon should be restored
      const existing = document.getElementById('existing-favicon') as HTMLLinkElement;
      expect(existing).toBeInTheDocument();
      expect(existing?.media).toBe('');
    });

    // Clean up
    existingFavicon.remove();
  });

  it('should handle fetch errors gracefully', async () => {
    process.env.NEXT_PUBLIC_BRAND_CONFIG_URL = '/brands/test/brand.json';
    (fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

    render(
      <BrandProvider>
        <TestComponent />
      </BrandProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Error: Network error/)).toBeInTheDocument();
    });
  });

  it('should handle invalid brand config gracefully', async () => {
    const invalidConfig = {
      // Missing required 'name' field
      logo: { componentPath: '/test/logo.js' }
    };

    process.env.NEXT_PUBLIC_BRAND_CONFIG_URL = '/brands/test/brand.json';
    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => invalidConfig
    });

    render(
      <BrandProvider>
        <TestComponent />
      </BrandProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Error: Invalid brand configuration format/)).toBeInTheDocument();
    });
  });

  it('should not cause React DOM errors when elements are removed', async () => {
    const mockConfig = {
      name: 'Test Brand',
      styles: { cssPath: '/test/styles.css' },
      favicon: { faviconPath: '/test/favicon.ico' }
    };

    process.env.NEXT_PUBLIC_BRAND_CONFIG_URL = '/brands/test/brand.json';
    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockConfig
    });

    const consoleError = jest.spyOn(console, 'error').mockImplementation(() => {});

    const { unmount, rerender } = render(
      <BrandProvider>
        <TestComponent />
      </BrandProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Brand: Test Brand')).toBeInTheDocument();
    });

    // Force re-render
    rerender(
      <BrandProvider>
        <TestComponent />
      </BrandProvider>
    );

    // Unmount
    unmount();

    // Wait a bit to ensure any async cleanup happens
    await waitFor(() => {
      // Check that no React DOM errors were logged
      const reactDomErrors = consoleError.mock.calls.filter(call => 
        call.some(arg => 
          typeof arg === 'string' && 
          (arg.includes('removeChild') || arg.includes('Cannot read properties of null'))
        )
      );
      expect(reactDomErrors).toHaveLength(0);
    });

    consoleError.mockRestore();
  });
});

