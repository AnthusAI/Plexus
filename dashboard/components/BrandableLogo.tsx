'use client';

import React from 'react';
import { useBrand } from '@/app/contexts/BrandContext';
import SquareLogo, { LogoVariant } from './logo-square';
import LogoErrorBoundary from './LogoErrorBoundary';

interface BrandableLogoProps {
  variant: LogoVariant;
  className?: string;
  shadowEnabled?: boolean;
  shadowWidth?: string;
  shadowIntensity?: number;
}

/**
 * Logo component that can be white-labeled via brand configuration.
 * Falls back to default Plexus logo if no custom logo is configured.
 */
export default function BrandableLogo({
  variant,
  className,
  shadowEnabled,
  shadowWidth,
  shadowIntensity,
}: BrandableLogoProps) {
  const { customLogoComponent, logoLoading } = useBrand();

  // If custom logo is loaded, use it; otherwise use default
  const LogoComponent = customLogoComponent || SquareLogo;
  
  // Custom logos should not have shadow effects by default
  const effectiveShadowEnabled = customLogoComponent ? false : shadowEnabled;

  return (
    <LogoErrorBoundary
      variant={variant}
      className={className}
      shadowEnabled={effectiveShadowEnabled}
      shadowWidth={shadowWidth}
      shadowIntensity={shadowIntensity}
    >
      <LogoComponent
        variant={variant}
        className={className}
        shadowEnabled={effectiveShadowEnabled}
        shadowWidth={shadowWidth}
        shadowIntensity={shadowIntensity}
      />
    </LogoErrorBoundary>
  );
}

