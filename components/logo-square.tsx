import React, { useEffect, useState, useMemo, useRef } from 'react';

enum LogoVariant {
  Square,
  Wide,
  Narrow
}

const gradientColors = [
  { position: 0, color: '#85cefa' },
  { position: 0.12, color: '#0389d7' },
  { position: 0.55, color: '#d03382' },
  { position: 1, color: '#85cefa' },
];

const getColorAtPosition = (position: number): string => {
  for (let i = 1; i < gradientColors.length; i++) {
    if (position <= gradientColors[i].position) {
      const prevColor = gradientColors[i - 1];
      const nextColor = gradientColors[i];
      const t = (position - prevColor.position) / (nextColor.position - prevColor.position);
      return interpolateColor(prevColor.color, nextColor.color, t);
    }
  }
  return gradientColors[gradientColors.length - 1].color;
};

const interpolateColor = (color1: string, color2: string, factor: number): string => {
  const r1 = parseInt(color1.slice(1, 3), 16);
  const g1 = parseInt(color1.slice(3, 5), 16);
  const b1 = parseInt(color1.slice(5, 7), 16);
  
  const r2 = parseInt(color2.slice(1, 3), 16);
  const g2 = parseInt(color2.slice(3, 5), 16);
  const b2 = parseInt(color2.slice(5, 7), 16);
  
  const r = Math.round(r1 + factor * (r2 - r1));
  const g = Math.round(g1 + factor * (g2 - g1));
  const b = Math.round(b1 + factor * (b2 - b1));
  
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
};

interface SquareLogoProps {
  variant: LogoVariant;
  className?: string;
}

const SquareLogo = ({ variant, className = '' }: SquareLogoProps) => {
  const columns = variant === LogoVariant.Wide ? 6 : variant === LogoVariant.Square ? 6 : 1;
  const rows = variant === LogoVariant.Square ? 6 : variant === LogoVariant.Wide ? 2 : 1;
  const containerRef = useRef<HTMLDivElement>(null);
  const [fontSize, setFontSize] = useState('16px');

  const cycleDuration = 80000;

  const [startTime] = useState(() => {
    const halfCycle = cycleDuration * 0.5;
    const additionalOffset = 30000;
    return Date.now() - (halfCycle + additionalOffset);
  });

  const [jitterValues, setJitterValues] = useState(() => 
    Array(rows * columns).fill(0).map(() => ({ value: Math.random() * 0.1 - 0.05, target: Math.random() * 0.1 - 0.05 }))
  );

  const randomOffsets = useMemo(() => 
    Array(rows * columns).fill(0).map(() => Math.random() * 0.2 - 0.1),
  [rows, columns]);

  const [grid, setGrid] = useState<string[]>(() =>
    Array(rows * columns).fill(0).map((_, index) => {
      const row = Math.floor(index / columns);
      const col = index % columns;
      const baseProgress = ((10 - (row + col)) / 10 + ((Date.now() - startTime) / cycleDuration)) % 1;
      const randomizedProgress = (baseProgress + randomOffsets[index] + jitterValues[index].value + 1) % 1;
      return getColorAtPosition(randomizedProgress);
    })
  );

  useEffect(() => {
    const animationInterval = setInterval(() => {
      setGrid(prevGrid => 
        prevGrid.map((_, index) => {
          const row = Math.floor(index / columns);
          const col = index % columns;
          const baseProgress = ((10 - (row + col)) / 10 + ((Date.now() - startTime) / cycleDuration)) % 1;
          const randomizedProgress = (baseProgress + randomOffsets[index] + jitterValues[index].value + 1) % 1;
          return getColorAtPosition(randomizedProgress);
        })
      );

      setJitterValues(prevJitterValues => 
        prevJitterValues.map(jitter => {
          const newValue = jitter.value + (jitter.target - jitter.value) * 0.05;
          if (Math.abs(newValue - jitter.target) < 0.001) {
            return { value: newValue, target: Math.random() * 0.1 - 0.05 };
          }
          return { ...jitter, value: newValue };
        })
      );
    }, 200);

    return () => clearInterval(animationInterval);
  }, [randomOffsets, startTime, columns, rows]);

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const containerWidth = containerRef.current.offsetWidth;
        const newFontSize = variant === LogoVariant.Wide ? 
          `${containerWidth / 3}px` :
          variant === LogoVariant.Narrow ?
            `${containerWidth * 1.4}px` :
            `${containerWidth / 3}px`;
        setFontSize(newFontSize);
      }
    };

    updateSize();
    window.addEventListener('resize', updateSize);

    const resizeObserver = new ResizeObserver(updateSize);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      window.removeEventListener('resize', updateSize);
      resizeObserver.disconnect();
    };
  }, [variant]);

  const containerStyle = {
    aspectRatio: `${columns} / ${rows}`,
  };

  const letterStyle = {
    fontFamily: "'Jersey 20', sans-serif",
    fontSize: fontSize,
    fontWeight: 400,
    color: 'white',
    position: 'absolute' as const,
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: variant === LogoVariant.Wide ? `${100 / columns}%` : '100%',
    textAlign: 'center' as const,
  };

  return (
    <div 
      ref={containerRef}
      className={`relative flex items-center justify-center overflow-hidden ${className}`} 
      style={containerStyle}
    >
      <div
        className={`absolute inset-0 grid ${
          variant === LogoVariant.Wide || variant === LogoVariant.Square ? 'grid-cols-6' : 'grid-cols-1'
        }`}
        style={{ gridTemplateRows: `repeat(${rows}, 1fr)` }}
      >
        {grid.map((color, index) => (
          <div
            key={index}
            className="w-full h-full"
            style={{ backgroundColor: color }}
          />
        ))}
      </div>
      {variant === LogoVariant.Wide || variant === LogoVariant.Square ? (
        <div className="absolute inset-0 flex">
          {['P', 'L', 'E', 'X', 'U', 'S'].map((letter, index) => (
            <span 
              key={letter} 
              style={{ 
                ...letterStyle, 
                left: `${((index + 0.53) * 100) / columns}%`,
                top: variant === LogoVariant.Square ? '50%' : '50%',
                width: `${100 / columns}%`,
              }}
            >
              {letter}
            </span>
          ))}
        </div>
      ) : (
        <div className="absolute inset-0 flex items-center justify-center">
          <span style={{ ...letterStyle, left: `55%`}}>P</span>
        </div>
      )}
    </div>
  );
};

export default SquareLogo;
export { LogoVariant };