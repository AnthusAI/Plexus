import React, { useEffect, useState, useMemo } from 'react';

const gradientColors = [
  { position: 0, color: '#85cefa' },
  { position: 0.12, color: '#0389d7' },
  { position: 0.55, color: '#d03382' },
  { position: 1, color: '#85cefa' },
];

const getColorAtPosition = (position) => {
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

const interpolateColor = (color1, color2, factor) => {
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

const SquareLogo = () => {
  const [grid, setGrid] = useState(Array(36).fill(''));
  const cycleDuration = 80000;
  const [startTime] = useState(() => {
    const halfCycle = cycleDuration * 0.5;
    const additionalOffset = 30000;
    return Date.now() - (halfCycle + additionalOffset);
  });
  const [jitterValues, setJitterValues] = useState(() => 
    Array(36).fill(0).map(() => ({ value: Math.random() * 0.1 - 0.05, target: Math.random() * 0.1 - 0.05 }))
  );

  const randomOffsets = useMemo(() => 
    Array(36).fill(0).map(() => Math.random() * 0.2 - 0.1),
  []);

  useEffect(() => {
    const animationInterval = setInterval(() => {
      setGrid(prevGrid => 
        prevGrid.map((_, index) => {
          const row = Math.floor(index / 6);
          const col = index % 6;
          const baseProgress = ((10 - (row + col)) / 10 + ((Date.now() - startTime) / cycleDuration)) % 1;
          const randomizedProgress = (baseProgress + randomOffsets[index] + jitterValues[index].value + 1) % 1;
          return getColorAtPosition(randomizedProgress);
        })
      );

      // Gradually update jitter values
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
  }, [randomOffsets, startTime]);

  const letterStyle = {
    fontFamily: "'Jersey 20', sans-serif",
    fontSize: '8rem',
    fontWeight: 400,
    color: 'white',
    position: 'absolute',
    top: '50%',
    transform: 'translate(3%, -50%)',
    width: '16.666%',
    textAlign: 'center',
  } as const;

  return (
    <div className="relative w-96 h-96 flex items-center justify-center overflow-hidden">
      <div className="absolute w-full h-full grid grid-cols-6 grid-rows-6">
        {grid.map((color, index) => (
          <div
            key={index}
            className="w-full h-full"
            style={{ backgroundColor: color }}
          />
        ))}
      </div>
      <div className="absolute inset-0">
        <span style={{...letterStyle, left: '0%'}}>P</span>
        <span style={{...letterStyle, left: '16.666%'}}>L</span>
        <span style={{...letterStyle, left: '33.333%'}}>E</span>
        <span style={{...letterStyle, left: '50%'}}>X</span>
        <span style={{...letterStyle, left: '66.666%'}}>U</span>
        <span style={{...letterStyle, left: '83.333%'}}>S</span>
      </div>
    </div>
  );
};

export default SquareLogo;