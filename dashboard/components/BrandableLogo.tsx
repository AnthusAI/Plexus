'use client';

import React from 'react';
import { useBrand } from '@/app/contexts/BrandContext';
import SquareLogo, { LogoVariant } from './logo-square';

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
  const { config } = useBrand();
  const logo = config?.logo;

  if (logo) {
    const src =
      variant === LogoVariant.Square
        ? logo.squarePath
        : variant === LogoVariant.Wide
          ? logo.widePath
          : logo.narrowPath;

    return (
      <img
        src={src}
        alt={logo.altText || `${config?.name || 'Brand'} logo`}
        className={className}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'contain',
          display: 'block',
        }}
      />
    );
  }

  return (
    <SquareLogo
      variant={variant}
      className={className}
      shadowEnabled={shadowEnabled}
      shadowWidth={shadowWidth}
      shadowIntensity={shadowIntensity}
    />
  );
}
