// Capacity custom logo component
// Plain JavaScript (no JSX) - works directly in the browser

import React from 'https://esm.sh/react@18';

// LogoVariant enum values from logo-square.tsx:
// Square = 0, Wide = 1, Narrow = 2
const LogoVariant = {
  Square: 0,
  Wide: 1,
  Narrow: 2
};

export default function CustomLogo({ variant, className }) {
  // variant is a numeric enum: 0 (Square), 1 (Wide), or 2 (Narrow)
  // For Square variant, show Capacity logo with "AI LAB" in a square
  // For Wide variant, show Capacity logo with "AI LAB" in a wide rectangle
  // For Narrow variant, show just "C" in a narrow rectangle
  
  console.log('[CustomLogo] Received variant:', variant, 'Type:', typeof variant);
  
  const isSquare = variant === LogoVariant.Square;
  const isWide = variant === LogoVariant.Wide;
  const isNarrow = variant === LogoVariant.Narrow;
  
  // Calculate aspect ratio based on variant
  // Square: 1:1, Wide: 3:1, Narrow: 1:1 (but smaller)
  const aspectRatio = isSquare ? '1 / 1' : 
                      isWide ? '3 / 1' : 
                      '1 / 1';
  
  // For narrow variant, show just "C"
  // For square and wide variants, show Capacity logo with "AI LAB" underneath
  if (isNarrow) {
    return React.createElement('div', {
      className: className,
      style: { 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        width: '100%',
        aspectRatio: aspectRatio,
        backgroundColor: 'white',
        color: '#1a1a1a',
        fontWeight: 'bold',
        fontSize: '2em',
        borderRadius: '8px',
        filter: 'none',
        boxShadow: 'none'
      }
    }, 'C');
  }
  
  // Square and wide variants with Capacity logo and "AI LAB"
  const ailabFontSize = isSquare ? '1.4em' : '0.9em';
  
  return React.createElement('div', {
    className: className,
    style: { 
      display: 'flex', 
      flexDirection: 'column',
      alignItems: 'center', 
      justifyContent: 'center',
      width: '100%',
      aspectRatio: aspectRatio,
      backgroundColor: 'white',
      borderRadius: '8px',
      filter: 'none',
      boxShadow: 'none',
      padding: '0.5em'
    }
  }, 
    React.createElement('div', {
      key: 'wrapper',
      style: {
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'stretch'
      }
    }, [
      React.createElement('img', {
        key: 'capacity-logo',
        src: '/brands/images/capacity-logo.png',
        alt: 'Capacity',
        style: {
          width: '100%',
          height: 'auto',
          marginBottom: '0.05em',
          objectFit: 'contain'
        }
      }),
      React.createElement('div', {
        key: 'ailab',
        style: {
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: ailabFontSize,
          fontWeight: 'bold',
          fontFamily: 'monospace',
          lineHeight: '1',
          color: '#1a1a1a'
        }
      }, 'AI LAB'.split('').map((letter, index) => 
        React.createElement('span', { key: index }, letter)
      ))
    ])
  );
}

