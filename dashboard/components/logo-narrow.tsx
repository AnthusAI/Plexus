import React from 'react';
import SquareLogo, { LogoVariant } from './logo-square';

interface NarrowLogoProps {
  className?: string;
}

const NarrowLogo = ({ className = '' }: NarrowLogoProps) => {
  return (
    <div className={`w-full aspect-square ${className}`}>
      <SquareLogo variant={LogoVariant.Narrow} className="w-full h-full" />
    </div>
  );
};

export default NarrowLogo;