import React from 'react';
import SquareLogo from './logo-square';

interface WideLogoProps {
  className?: string;
}

const WideLogo = ({ className = '' }: WideLogoProps) => {
  return (
    <SquareLogo wide className={`w-full ${className}`} />
  );
};

export default WideLogo;