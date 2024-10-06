import React, { useEffect, useState, useMemo, useRef } from 'react';

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
  wide?: boolean;
  className?: string;
}

const SquareLogo = ({ wide = false, className = '' }: SquareLogoProps) => {
  const columns = 6;
  const rows = wide ? 2 : 6;
  const containerRef = useRef<HTMLDivElement>(null);
  const [fontSize, setFontSize] = useState('16px');

  const cycleDuration = 80000;

  // Move startTime above grid initialization
  const [startTime] = useState(() => {
    const halfCycle = cycleDuration * 0.5;
    const additionalOffset = 30000;
    return Date.now() - (halfCycle + additionalOffset);
  });

  // Move jitterValues above grid initialization
  const [jitterValues, setJitterValues] = useState(() => 
    Array(rows * columns).fill(0).map(() => ({ value: Math.random() * 0.1 - 0.05, target: Math.random() * 0.1 - 0.05 }))
  );

  // Move randomOffsets above grid initialization
  const randomOffsets = useMemo(() => 
    Array(rows * columns).fill(0).map(() => Math.random() * 0.2 - 0.1),
  [rows, columns]);

  // Initialize grid after defining dependencies
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
        const newFontSize = wide ? 
          `${containerWidth / 3}px` : // This remains unchanged for the wide variant
          `${containerWidth / 3}px`; // Changed from 4 to 2.67 to increase size by ~1.5x
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
  }, [wide]);

  const containerStyle = {
    aspectRatio: `${columns} / ${rows}`,
  };

  const letterStyle = {
    fontFamily: "'Jersey 20', sans-serif",
    fontSize: fontSize,
    fontWeight: 400,
    color: 'white',
    position: 'absolute',
    top: '50%',
    transform: 'translate(-50%, -50%)',
    width: `${100 / columns}%`,
    textAlign: 'center',
  } as const;

  return (
    <div 
      ref={containerRef}
      className={`relative flex items-center justify-center overflow-hidden ${className}`} 
      style={containerStyle}
    >
      <div
        className="absolute inset-0 grid grid-cols-6"
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
      <div className="absolute inset-0 flex">
        {['P', 'L', 'E', 'X', 'U', 'S'].map((letter, index) => (
          <span key={letter} style={{ ...letterStyle, left: `${((index + 0.53) * 100) / columns}%` }}>
            {letter}
          </span>
        ))}
      </div>
    </div>
  );
};

export default SquareLogo;