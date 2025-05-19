"use client";

import React, { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import { CardButton } from '@/components/CardButton';
import { Gauge, type Segment } from '@/components/gauge';
import { cn } from '@/lib/utils';
import ClassDistributionVisualizer, { type ClassDistribution } from '@/components/ClassDistributionVisualizer';
import PredictedClassDistributionVisualizer from '@/components/PredictedClassDistributionVisualizer';
import { ConfusionMatrix, type ConfusionMatrixData } from '@/components/confusion-matrix';
import { GaugeThresholdComputer } from '@/utils/gauge-thresholds';
import { RawAgreementBar } from '@/components/RawAgreementBar';

// Export the AC1 gauge segments for reuse in other components
export const ac1GaugeSegments: Segment[] = [
  { start: 0, end: 50, color: 'var(--gauge-inviable)' },      // Negative values (-1 to 0)
  { start: 50, end: 60, color: 'var(--gauge-converging)' },   // Low alignment (0 to 0.2)
  { start: 60, end: 75, color: 'var(--gauge-almost)' },       // Moderate alignment (0.2 to 0.5)
  { start: 75, end: 90, color: 'var(--gauge-viable)' },       // Good alignment (0.5 to 0.8)
  { start: 90, end: 100, color: 'var(--gauge-great)' }        // Excellent alignment (0.8 to 1.0)
];

export interface ScorecardReportEvaluationData {
  id: string;
  question?: string;
  score_name: string;
  cc_question_id?: string;
  ac1?: number | null;
  total_items?: number;
  item_count?: number;
  mismatches?: number;
  accuracy?: number;
  precision?: number;
  recall?: number;
  label_distribution?: Record<string, number>;
  class_distribution?: ClassDistribution[];
  predicted_class_distribution?: ClassDistribution[];
  confusion_matrix?: ConfusionMatrixData;
  warning?: string;
  notes?: string;
  discussion?: string;
}

interface ScorecardReportEvaluationProps {
  score: ScorecardReportEvaluationData;
  className?: string;
  showPrecisionRecall?: boolean;
}

export const ScorecardReportEvaluation: React.FC<ScorecardReportEvaluationProps> = ({ 
  score,
  className,
  showPrecisionRecall = true
}) => {
  const [expanded, setExpanded] = useState(false);
  
  // Helper function to get agreement level text and color
  const getAgreementLevel = (ac1: number | null): { label: string; color: string } => {
    if (ac1 === null) return { label: 'No Data', color: 'bg-muted text-muted-foreground' };
    if (ac1 >= 0.8) return { label: 'Strong', color: 'bg-green-700 text-white' };
    if (ac1 >= 0.6) return { label: 'Moderate', color: 'bg-yellow-600 text-white' };
    if (ac1 >= 0.4) return { label: 'Fair', color: 'bg-orange-500 text-white' }; 
    if (ac1 >= 0.0) return { label: 'Slight', color: 'bg-red-400 text-white' };
    return { label: 'Poor', color: 'bg-red-700 text-white' };
  };

  const level = score.ac1 !== undefined ? getAgreementLevel(score.ac1) : { label: 'N/A', color: 'bg-muted text-muted-foreground' };
  const displayName = score.score_name || score.question || 'Unnamed Score';
  const itemCount = score.total_items || score.item_count || 0;
  const mismatches = score.mismatches || 0;
  const agreements = itemCount - mismatches;
  const agreementPercent = itemCount > 0 ? (agreements / itemCount) * 100 : 0;
  const hasWarning = !!score.warning;
  const hasNotes = !!score.notes;
  const hasDiscussion = !!score.discussion;
  const hasItems = itemCount > 0;
  
  // Calculate accuracy segments if label distribution is available
  const accuracySegments: Segment[] = score.label_distribution 
    ? GaugeThresholdComputer.createSegments(
        GaugeThresholdComputer.computeThresholds(score.label_distribution)
      )
    : [{ start: 0, end: 100, color: 'var(--gauge-inviable)' }];
  
  // Determine if we have visualization data available
  const hasClassDistribution = score.class_distribution && score.class_distribution.length > 0;
  const hasPredictedDistribution = score.predicted_class_distribution && score.predicted_class_distribution.length > 0;
  const hasConfusionMatrix = score.confusion_matrix !== undefined;
  const hasVisualizationData = hasClassDistribution || hasPredictedDistribution || hasConfusionMatrix;
  
  // Determine if we have extra data to show in expanded view
  // Now we always allow expansion if there's any items data to show raw agreement bars
  const hasExtendedData = hasVisualizationData || hasDiscussion || hasItems;
  
  return (
    <div className={cn(
      "transition-all bg-card rounded-lg relative", 
      expanded ? "mb-6" : "mb-2",
      className
    )}>
      <div className="p-4">
        {/* Header row with title and expand/collapse button */}
        <div className="flex justify-between items-start mb-4">
          <h3 className="text-base font-medium">{displayName}</h3>
          {hasExtendedData && (
            <CardButton 
              icon={expanded ? ChevronUp : ChevronDown}
              onClick={() => setExpanded(!expanded)}
              aria-label={expanded ? "Collapse details" : "Expand details"}
              className="ml-2"
            />
          )}
        </div>
        
        {/* Main content area - responsive grid layout */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-start">
          {/* Left side - metadata */}
          <div className="md:col-span-4">
            <div className="text-sm space-y-1">
              {itemCount > 0 && (
                <>
                  <div>
                    <span className="text-muted-foreground">Agreements:</span>{' '}
                    <span>{agreements}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Items:</span>{' '}
                    <span>{itemCount}</span>
                  </div>
                </>
              )}
            </div>
            
            {/* Notes section - shown in both collapsed and expanded views */}
            {hasNotes && (
              <div className="mt-3 text-sm">
                <p className="text-foreground">{score.notes}</p>
              </div>
            )}
          </div>
          
          {/* Right side - Gauges */}
          <div className="md:col-span-8">
            <div className="@container">
              <div className="grid grid-cols-1 @xs:grid-cols-2 @lg:grid-cols-4 gap-3">
                {/* AC1 Gauge - Only show if ac1 is available */}
                {score.ac1 !== undefined && (
                  <div className="flex flex-col items-center">
                    <div className="w-full max-w-[140px] mx-auto">
                      <Gauge 
                        value={score.ac1 ?? 0} 
                        title="Agreement"
                        valueUnit=""
                        min={-1}
                        max={1}
                        decimalPlaces={2}
                        segments={ac1GaugeSegments}
                      />
                    </div>
                  </div>
                )}
                
                {/* Accuracy Gauge - Only show if accuracy is available */}
                {score.accuracy !== undefined && (
                  <div className="flex flex-col items-center">
                    <div className="w-full max-w-[140px] mx-auto">
                      <Gauge 
                        value={score.accuracy ?? 0} 
                        title="Accuracy"
                        segments={accuracySegments}
                      />
                    </div>
                  </div>
                )}
                
                {/* Precision Gauge - Only show if precision is available and showPrecisionRecall is true */}
                {showPrecisionRecall && score.precision !== undefined && (
                  <div className="flex flex-col items-center">
                    <div className="w-full max-w-[140px] mx-auto">
                      <Gauge 
                        value={score.precision ?? 0} 
                        title="Precision"
                        segments={accuracySegments}
                      />
                    </div>
                  </div>
                )}
                
                {/* Recall Gauge - Only show if recall is available and showPrecisionRecall is true */}
                {showPrecisionRecall && score.recall !== undefined && (
                  <div className="flex flex-col items-center">
                    <div className="w-full max-w-[140px] mx-auto">
                      <Gauge 
                        value={score.recall ?? 0} 
                        title="Recall"
                        segments={accuracySegments}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
        
        {/* Warning message - below the gauges */}
        {hasWarning && (
          <div className="mt-4 bg-red-600 text-white p-3 rounded-sm w-full">
            <div className="flex items-start gap-2">
              <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
              <p className="text-sm font-medium">{score.warning}</p>
            </div>
          </div>
        )}
      </div>
      
      {/* Expanded View */}
      {expanded && (
        <div className="px-4 pb-4">
          {/* Visualizations */}
          {hasVisualizationData && (
            <div className="space-y-6">
              {hasClassDistribution && (
                <div>
                  <h5 className="text-sm font-medium mb-2">Class Distribution</h5>
                  <ClassDistributionVisualizer 
                    data={score.class_distribution!} 
                    isBalanced={false} 
                  />
                </div>
              )}
              
              {hasPredictedDistribution && (
                <div>
                  <h5 className="text-sm font-medium mb-2">Predicted Class Distribution</h5>
                  <PredictedClassDistributionVisualizer 
                    data={score.predicted_class_distribution!}
                  />
                </div>
              )}
              
              {hasConfusionMatrix && (
                <div>
                  <h5 className="text-sm font-medium mb-2">Confusion Matrix</h5>
                  <ConfusionMatrix data={score.confusion_matrix!} />
                </div>
              )}
              
              {/* Raw Agreement Bar */}
              {hasItems && (
                <div>
                  <h5 className="text-sm font-medium mb-2">Raw Agreement</h5>
                  <RawAgreementBar 
                    agreements={agreements}
                    totalItems={itemCount}
                  />
                </div>
              )}
              
              {/* Discussion section - only shown in expanded view */}
              {hasDiscussion && (
                <div className="mt-6">
                  <div className="text-sm prose-sm max-w-none">
                    <p>{score.discussion}</p>
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* If there's no visualization data but there is discussion, show only discussion */}
          {!hasVisualizationData && hasDiscussion && (
            <div className="space-y-6">
              <div className="pt-2">
                <div className="text-sm prose-sm max-w-none">
                  <p>{score.discussion}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Expanded View section for when there's only raw agreement bars to show */}
      {expanded && !hasVisualizationData && !hasDiscussion && hasItems && (
        <div className="px-4 pb-4">
          <div className="space-y-6">
            <div>
              <h5 className="text-sm font-medium mb-2">Raw Agreement</h5>
              <RawAgreementBar 
                agreements={agreements}
                totalItems={itemCount}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Compatibility alias for backward compatibility
export const ScorecardEvaluation = ScorecardReportEvaluation;

export default ScorecardReportEvaluation; 