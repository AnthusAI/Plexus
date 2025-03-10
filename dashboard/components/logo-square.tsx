import React, { useEffect, useState, useMemo, useRef } from 'react';
import { motion } from "framer-motion"

enum LogoVariant {
  Square,
  Wide,
  Narrow
}

const gradientColors = [
  { position: 0, color: '#5EB1EF' },
  { position: 0.12, color: '#0D74CE' },
  { position: 0.55, color: '#C2298A' },
  { position: 1, color: '#5EB1EF' },
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
  const columns = variant === LogoVariant.Wide ? 6 : 
                 variant === LogoVariant.Square ? 6 : 
                 2;  // 2x2 grid for Narrow
  const rows = variant === LogoVariant.Square ? 6 : 
              variant === LogoVariant.Wide ? 2 : 
              2;  // 2x2 grid for Narrow
  const containerRef = useRef<HTMLDivElement>(null);
  const [fontSize, setFontSize] = useState('16px');
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  const cycleDuration = 80000;

  const [startTime] = useState(() => {
    const halfCycle = cycleDuration * 0.5;
    const additionalOffset = 30000;
    return Date.now() - (halfCycle + additionalOffset);
  });

  const [jitterValues] = useState(() => 
    Array(rows * columns).fill(0).map(() => ({ value: Math.random() * 0.1 - 0.05, target: Math.random() * 0.1 - 0.05 }))
  );

  const randomOffsets = useMemo(() => 
    Array(rows * columns).fill(0).map(() => Math.random() * 0.2 - 0.1),
  [rows, columns]);

  // Compute current and next colors for each cell
  const [colorStates, setColorStates] = useState(() => 
    Array(rows * columns).fill(0).map((_, index) => {
      const row = Math.floor(index / columns);
      const col = index % columns;
      const baseProgress = (10 - (row + col)) / 10;
      const currentProgress = (baseProgress + ((Date.now() - startTime) / cycleDuration)) % 1;
      const nextProgress = (currentProgress + (250 / cycleDuration)) % 1;
      return {
        current: getColorAtPosition((currentProgress + randomOffsets[index] + jitterValues[index].value + 1) % 1),
        next: getColorAtPosition((nextProgress + randomOffsets[index] + jitterValues[index].value + 1) % 1)
      };
    })
  );

  useEffect(() => {
    if (!isClient) return;

    const updateColors = () => {
      setColorStates(prev => 
        prev.map((_, index) => {
          const row = Math.floor(index / columns);
          const col = index % columns;
          const baseProgress = ((10 - (row + col)) / 10 + ((Date.now() - startTime) / cycleDuration)) % 1;
          const currentProgress = (baseProgress + randomOffsets[index] + jitterValues[index].value + 1) % 1;
          const nextProgress = (currentProgress + (250 / cycleDuration)) % 1;
          return {
            current: getColorAtPosition(currentProgress),
            next: getColorAtPosition(nextProgress)
          };
        })
      );
    };

    const interval = setInterval(updateColors, 250);
    return () => clearInterval(interval);
  }, [isClient, columns, startTime, cycleDuration, randomOffsets, jitterValues]);

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const containerWidth = containerRef.current.offsetWidth;
        const newFontSize = variant === LogoVariant.Wide ? 
          `${containerWidth / 2.8}px` :
          variant === LogoVariant.Narrow ?
            `${containerWidth / 0.65}px` :  // Compromise size for narrow variant
            `${containerWidth / 2.8}px`;  // Slightly smaller for square variant
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

  return (
    <div 
      ref={containerRef}
      className={className}
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${columns}, 1fr)`,
        gridTemplateRows: `repeat(${rows}, 1fr)`,
        aspectRatio: `${columns} / ${rows}`,
        position: 'relative',
        minWidth: '100%',
        minHeight: '100%',
      }}
    >
      {/* Background color grid */}
      <div 
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
          gridTemplateRows: `repeat(${rows}, 1fr)`,
          gridArea: '1 / 1 / -1 / -1',
        }}
      >
        {colorStates.map((colors, index) => (
          <motion.div
            key={index}
            initial={{ backgroundColor: colors.current }}
            animate={{ backgroundColor: colors.next }}
            transition={{ 
              duration: 0.25,
              ease: "linear"
            }}
          />
        ))}
      </div>

      {/* Letters overlay */}
      <div 
        style={{
          position: 'relative',
          gridArea: '1 / 1 / -1 / -1',
          width: '100%',
          height: '100%',
        }}
      >
        {variant === LogoVariant.Wide || variant === LogoVariant.Square ? (
          ['P', 'L', 'E', 'X', 'U', 'S'].map((letter, index) => (
            <span
              key={letter}
              style={{
                fontFamily: "'Jersey 20', sans-serif",
                fontSize: fontSize,
                fontWeight: 400,
                color: 'var(--muted)',
                lineHeight: 1.2,
                position: 'absolute',
                left: `${(index + 0.5) * (100 / 6) + (100 / 6 / 40)}%`,  // Center + 1/40 column width
                top: '50%',
                transform: 'translate(-50%, -50%)',  // Center the letter on its point
              }}
            >
              {letter}
            </span>
          ))
        ) : (
          <span
            style={{
              fontFamily: "'Jersey 20', sans-serif",
              fontSize: fontSize,
              fontWeight: 400,
              color: 'var(--muted)',
              lineHeight: 1.2,
              position: 'absolute',
              left: `${54 + (100 / 6 / 40)}%`,  // Shifted slightly more right for narrow variant
              top: '53.5%',  // Shifted more down for narrow variant
              transform: 'translate(-50%, -50%)',
            }}
          >
            P
          </span>
        )}
      </div>
    </div>
  );
};

export default SquareLogo;
export { LogoVariant };