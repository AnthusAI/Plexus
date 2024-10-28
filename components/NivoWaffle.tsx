'use client';

import { ResponsiveWaffle } from '@nivo/waffle'

export interface NivoWaffleProps {
  processedItems: number;
  totalItems: number;
  accuracy: number;
}

const NivoWaffle: React.FC<NivoWaffleProps> = ({ processedItems, totalItems, accuracy }) => {
  console.log('NivoWaffle props:', { processedItems, totalItems, accuracy });

  const scale = totalItems > 100 ? 100 / totalItems : 1;
  const scaledTotal = Math.min(totalItems, 100);
  const scaledProcessed = Math.min(Math.round(processedItems * scale), scaledTotal);

  const correctItems = Math.round(scaledProcessed * accuracy / 100);
  const incorrectItems = scaledProcessed - correctItems;
  const unprocessedItems = scaledTotal - scaledProcessed;

  const data = [
    { id: 'correct', label: 'Correct', value: correctItems },
    { id: 'incorrect', label: 'Incorrect', value: incorrectItems },
    { id: 'unprocessed', label: 'Unprocessed', value: unprocessedItems },
  ];

  console.log('NivoWaffle data:', data);

  const customColors = {
    unprocessed: 'var(--neutral)',
    correct: 'var(--true)',
    incorrect: 'var(--false)'
  }

  if (data.some(item => isNaN(item.value) || item.value < 0)) {
    console.error('Invalid data for NivoWaffle:', data);
    return <div>Error: Invalid data for waffle chart</div>;
  }

  return (
    <ResponsiveWaffle
        data={data}
        total={scaledTotal}
        rows={5}
        columns={20}
        padding={1}
        colors={({ id }) => customColors[id as keyof typeof customColors]}
        borderColor={{ from: 'color', modifiers: [['darker', 0.3]] }}
        emptyColor="var(--bg-muted)"
        emptyOpacity={0.5}
        fillDirection="right"
        legends={[
            {
            anchor: 'bottom',
            direction: 'row',
            justify: false,
            translateX: 0,
            translateY: 30,
            itemsSpacing: 4,
            itemWidth: 100,
            itemHeight: 20,
            itemDirection: 'left-to-right',
            itemOpacity: 1,
            itemTextColor: 'var(--text-muted)',
            symbolSize: 20,
            effects: [
                {
                on: 'hover',
                style: {
                    itemTextColor: 'var(--text-foreground)',
                    itemBackground: 'var(--bg-card)'
                }
                }
            ]
            }
        ]}
    />
  )
}

export default NivoWaffle
