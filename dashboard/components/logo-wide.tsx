import React from 'react';
import SquareLogo, { LogoVariant } from './logo-square';

interface WideLogoProps {
  className?: string;
}

const WideLogo = ({ className = '' }: WideLogoProps) => {
  return (
    <SquareLogo variant={LogoVariant.Wide} className={`w-full ${className}`} />
  );
};

export default WideLogo;