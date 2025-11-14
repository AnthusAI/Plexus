'use client';

import { useEffect } from 'react';
import { useBrand } from '@/app/contexts/BrandContext';

interface BrandedTitleProps {
  pageTitle?: string;
}

/**
 * Client component that updates the document title based on brand configuration.
 * Falls back to "Plexus" if no brand name is configured.
 * 
 * Uses a MutationObserver to watch for title changes and replace "Plexus" with the brand name.
 */
export function BrandedTitle({ pageTitle }: BrandedTitleProps) {
  const { config } = useBrand();
  const brandName = config?.name || 'Plexus';

  useEffect(() => {
    // If no custom brand is configured, don't do anything
    // Let Next.js handle the title normally
    if (!config?.name) {
      console.log('[BrandedTitle] No custom brand configured, using default title handling');
      return;
    }

    const replacePlexusInTitle = () => {
      const currentTitle = document.title;
      console.log('[BrandedTitle] Current title:', currentTitle);
      
      if (pageTitle) {
        // If a specific page title is provided, use it
        const newTitle = `${pageTitle} - ${brandName}`;
        if (currentTitle === newTitle) {
          console.log('[BrandedTitle] Title already correct, skipping update');
          return;
        }
        console.log('[BrandedTitle] Setting title from pageTitle prop:', newTitle);
        document.title = newTitle;
      } else if (currentTitle && currentTitle.includes('Plexus')) {
        // Replace "Plexus" with the brand name in the existing title
        // This handles cases like "Tasks - Plexus" or "Evaluations -- Plexus"
        const brandedTitle = currentTitle.replace(/Plexus/g, brandName);
        if (currentTitle === brandedTitle) {
          console.log('[BrandedTitle] Title already correct, skipping update');
          return;
        }
        console.log('[BrandedTitle] Replacing Plexus with', brandName, ':', brandedTitle);
        document.title = brandedTitle;
      } else if (currentTitle && !currentTitle.includes(brandName)) {
        // If the title doesn't contain the brand name, append it
        // This handles cases like "Agent Operating System" -> "Agent Operating System - Acme"
        const brandedTitle = `${currentTitle} - ${brandName}`;
        if (currentTitle === brandedTitle) {
          console.log('[BrandedTitle] Title already correct, skipping update');
          return;
        }
        console.log('[BrandedTitle] Appending brand name to title:', brandedTitle);
        document.title = brandedTitle;
      } else {
        console.log('[BrandedTitle] Title already contains brand name, leaving as is');
      }
    };

    // Initial replacement
    replacePlexusInTitle();

    // Also replace on multiple delays to catch any async title updates
    const timeoutId1 = setTimeout(replacePlexusInTitle, 100);
    const timeoutId2 = setTimeout(replacePlexusInTitle, 500);
    const timeoutId3 = setTimeout(replacePlexusInTitle, 1000);

    // Watch for title changes by observing the entire head element
    // This catches changes to the title element itself
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        // Check if any of the mutations affected the title
        if (mutation.type === 'childList') {
          const titleChanged = Array.from(mutation.addedNodes).some(
            (node) => node.nodeName === 'TITLE'
          ) || Array.from(mutation.removedNodes).some(
            (node) => node.nodeName === 'TITLE'
          );
          
          if (titleChanged || mutation.target.nodeName === 'TITLE') {
            console.log('[BrandedTitle] Title element changed, re-checking');
            replacePlexusInTitle();
          }
        } else if (mutation.type === 'characterData' && mutation.target.parentNode?.nodeName === 'TITLE') {
          console.log('[BrandedTitle] Title text changed, re-checking');
          replacePlexusInTitle();
        }
      });
    });

    // Observe both the head and the title element
    const headElement = document.head;
    const titleElement = document.querySelector('title');
    
    if (headElement) {
      observer.observe(headElement, {
        childList: true,
        subtree: true,
        characterData: true,
      });
    }
    
    if (titleElement) {
      observer.observe(titleElement, {
        childList: true,
        characterData: true,
        subtree: true,
      });
    }

    // Cleanup
    return () => {
      clearTimeout(timeoutId1);
      clearTimeout(timeoutId2);
      clearTimeout(timeoutId3);
      observer.disconnect();
    };
  }, [pageTitle, brandName]);

  return null; // This component doesn't render anything
}

