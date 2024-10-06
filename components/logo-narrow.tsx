import React from 'react';
import SquareLogo from './logo-square';

interface NarrowLogoProps {
  className?: string;
}

const NarrowLogo = ({ className = '' }: NarrowLogoProps) => {
  return (
    <div className={`w-full aspect-square ${className}`}>
      <SquareLogo wide={false} className="w-full h-full" />
    </div>
  );
};

export default NarrowLogo;