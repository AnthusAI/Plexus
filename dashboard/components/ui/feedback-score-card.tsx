import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Gauge, Segment } from '@/components/gauge';
import { GaugeThresholdComputer } from '@/utils/gauge-thresholds';

// Score data interface
export interface ScoreData {
  id: string;
  score_name: string;
  cc_question_id?: string;
  ac1: number | null;
  item_count: number;
  mismatches: number;
  mismatch_percentage?: number;
  accuracy?: number;
  label_distribution?: Record<string, number>;
}

// Define AC1 segments (percentages of the -1 to 1 range)
export const ac1GaugeSegments: Segment[] = [
  { start: 0, end: 50, color: 'var(--gauge-inviable)' },   // AC1: -1.0 to 0.0
  { start: 50, end: 70, color: 'var(--gauge-converging)' }, // AC1: 0.0 to 0.4
  { start: 70, end: 80, color: 'var(--gauge-almost)' },    // AC1: 0.4 to 0.6
  { start: 80, end: 90, color: 'var(--gauge-viable)' },    // AC1: 0.6 to 0.8
  { start: 90, end: 100, color: 'var(--gauge-great)' },   // AC1: 0.8 to 1.0
];

/**
 * FeedbackScoreCard component for displaying feedback score metrics with alignment (AC1) and accuracy gauges
 */
export const FeedbackScoreCard: React.FC<{
  score: ScoreData;
  className?: string;
}> = ({ score, className }) => {
  // Function to create accuracy gauge segments based on label distribution
  const getAccuracySegments = (labelDistribution?: Record<string, number>): Segment[] => {
    if (!labelDistribution) {
      // Default segments if no distribution data available
      return [
        { start: 0, end: 60, color: 'var(--gauge-inviable)' },
        { start: 60, end: 70, color: 'var(--gauge-converging)' },
        { start: 70, end: 80, color: 'var(--gauge-almost)' },
        { start: 80, end: 90, color: 'var(--gauge-viable)' },
        { start: 90, end: 100, color: 'var(--gauge-great)' }
      ];
    }
    
    // Compute dynamic thresholds based on class distribution
    const thresholds = GaugeThresholdComputer.computeThresholds(labelDistribution);
    
    // Create segments from the computed thresholds
    return GaugeThresholdComputer.createSegments(thresholds);
  };
  
  // Function to create gauge information tooltip based on label distribution
  const getGaugeInformation = (labelDistribution?: Record<string, number>): string | undefined => {
    if (!labelDistribution) {
      return undefined;
    }
    
    const thresholds = GaugeThresholdComputer.computeThresholds(labelDistribution);
    
    return `Dynamic thresholds based on class distribution:
- Chance level (baseline): ${thresholds.chance.toFixed(1)}%
- Okay: chance +20% (${thresholds.okayThreshold.toFixed(1)}%)
- Good: chance +30% (${thresholds.goodThreshold.toFixed(1)}%)
- Great: chance +40% (${thresholds.greatThreshold.toFixed(1)}%)
- Perfect: chance +45% (${thresholds.perfectThreshold.toFixed(1)}%) and above`;
  };

  const agreements = score.item_count - score.mismatches;
  // Get accuracy segments based on this score's label distribution
  const accuracySegments = getAccuracySegments(score.label_distribution);
  const gaugeInfo = getGaugeInformation(score.label_distribution);
  
  return (
    <Card className={`bg-card shadow-none border-none ${className || ''}`}>
      <CardHeader>
        <CardTitle className="font-bold">{score.score_name}</CardTitle>
        <p className="text-sm text-muted-foreground">
          {agreements} agreement{agreements === 1 ? '' : 's'} / {score.item_count} feedback item{score.item_count === 1 ? '' : 's'}
        </p>
      </CardHeader>
      <CardContent className="flex flex-col sm:flex-row justify-around items-center gap-4 pt-2 pb-4">
        <div className="w-full sm:w-1/2 max-w-[200px] sm:max-w-none">
          <Gauge
            title="Agreement"
            value={score.ac1 ?? undefined}
            min={-1}
            max={1}
            segments={ac1GaugeSegments}
            showTicks={false}
          />
        </div>
        <div className="w-full sm:w-1/2 max-w-[200px] sm:max-w-none">
          <Gauge
            title="Accuracy"
            value={score.accuracy ?? undefined}
            segments={accuracySegments}
            information={gaugeInfo}
            showTicks={false}
          />
        </div>
      </CardContent>
    </Card>
  );
};

export default FeedbackScoreCard; 