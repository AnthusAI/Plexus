import React from 'react';
import { GaugeThresholdComputer } from '@/utils/gauge-thresholds';
import ReportBlock, { ReportBlockProps } from './ReportBlock';
import { ScorecardReportEvaluation, ScorecardReportEvaluationData, ac1GaugeSegments } from '@/components/ui/scorecard-evaluation';
import { RawAgreementBar } from '@/components/RawAgreementBar';
import { Gauge, type Segment } from '@/components/gauge';

// For type-safety, create an interface for the data structure
export interface ScorecardReportData {
  scores: ScorecardReportEvaluationData[];
  total_items: number;
  total_agreements: number;
  mismatch_percentage?: number;
  accuracy?: number;
  overall_agreement?: number | null;
  date_range?: {
    start: string;
    end: string;
  };
  label_distribution?: Record<string, number>;
  warning?: string;
  error?: string;
  rawOutput?: string | null;
  log?: string | null;
  attachedFiles?: string[] | null;
}

export interface ScorecardReportProps extends ReportBlockProps {
  showDateRange?: boolean;
  showPrecisionRecall?: boolean;
  onCellSelection?: (selection: { predicted: string | null; actual: string | null }) => void;
  drillDownContent?: React.ReactNode;
  showTitle?: boolean;
  // Props for on-demand analysis drill-down
  scorecardId?: string;
  accountId?: string;
}

/**
 * Component for rendering scorecard reports with evaluation results.
 * Extends the base ReportBlock component for common functionality like
 * title, logs, attached files, and errors/warnings handling.
 */
const ScorecardReport: React.FC<ScorecardReportProps> = ({ 
  output, 
  showDateRange = true,
  showPrecisionRecall = true,
  onCellSelection,
  drillDownContent,
  showTitle,
  scorecardId,
  accountId,
  children,
  ...restProps
}) => {
  // Cast to the expected data type
  const scoreData = output as ScorecardReportData;
  
  if (!scoreData) {
    return <p>No scorecard data available or data is loading.</p>;
  }

  const hasData = scoreData.scores && scoreData.scores.length > 0;
  const showSummary = hasData && scoreData.scores.length > 1;

  // Calculate accuracy segments if label distribution is available
  const accuracySegments: Segment[] = scoreData.label_distribution 
    ? GaugeThresholdComputer.createSegments(
        GaugeThresholdComputer.computeThresholds(scoreData.label_distribution)
      )
    : [{ start: 0, end: 100, color: 'var(--gauge-inviable)' }];

  // Calculate accuracy value  
  const accuracy = scoreData.accuracy !== undefined 
    ? scoreData.accuracy 
    : scoreData.mismatch_percentage !== undefined
      ? (100 - scoreData.mismatch_percentage)
      : scoreData.total_items > 0
        ? (scoreData.total_agreements / scoreData.total_items) * 100
        : 100.0;

  // Calculate average precision and recall
  const calculateAverage = (property: 'precision' | 'recall'): number => {
    if (!hasData) return 0;
    
    const values = scoreData.scores
      .map(score => score[property])
      .filter((value): value is number => value !== undefined && value !== null);
    
    if (values.length === 0) return 0;
    return values.reduce((sum, value) => sum + value, 0) / values.length;
  };
  
  const averagePrecision = calculateAverage('precision');
  const averageRecall = calculateAverage('recall');

  // Determine which gauges to show in the summary
  const hasAgreementGauge = typeof scoreData.overall_agreement === 'number';
  const hasAccuracyGauge = typeof accuracy === 'number';
  const hasPrecisionGauge = showPrecisionRecall && averagePrecision > 0;
  const hasRecallGauge = showPrecisionRecall && averageRecall > 0;

  // Prepare the content to pass to the ReportBlock
  const scoreCardContent = (
    <>
      {/* Score Cards Section - Updated to use responsive container queries */}
      {hasData && scoreData.scores.length > 0 && (
        <div className="@container">
          <div className="grid grid-cols-1 @[60rem]:grid-cols-2 gap-3">
            {scoreData.scores
              .map((scoreItem, originalIdx) => ({ // Add originalIndex before sorting
                scoreData: scoreItem,
                originalIndex: originalIdx
              }))
              .sort((a, b) => {
                // Sort by accuracy if available, otherwise sorting can be customized
                // Now access accuracy via a.scoreData.accuracy
                if (a.scoreData.accuracy === undefined && b.scoreData.accuracy !== undefined) return 1;
                if (a.scoreData.accuracy !== undefined && b.scoreData.accuracy === undefined) return -1;
                if (a.scoreData.accuracy !== undefined && b.scoreData.accuracy !== undefined) {
                  return b.scoreData.accuracy - a.scoreData.accuracy;
                }
                return 0;
              })
              .map((item, sortedMapIndex) => ( // item now contains scoreData and originalIndex
                <ScorecardReportEvaluation 
                  key={item.scoreData.id || `score-eval-${item.originalIndex}`} // Use originalIndex or id for a stable key
                  score={item.scoreData}
                  scoreIndex={item.originalIndex} // Pass the ORIGINAL index
                  attachedFiles={restProps.attachedFiles}
                  showPrecisionRecall={showPrecisionRecall}
                  onCellSelection={onCellSelection}
                  scorecardId={scorecardId}
                  accountId={accountId}
                  isSingleScore={scoreData.scores.length === 1}
                />
              ))}
          </div>
        </div>
      )}

      {/* Summary Card - Conditionally Rendered with flat styling */}
      {showSummary && (
        <div className="bg-card rounded-lg p-4 mt-4">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-base font-medium">Summary</h3>
          </div>
          
          <div className="@container">
            <div className="grid grid-cols-1 @[30rem]:grid-cols-12 gap-3 items-start">
              <div className="@[30rem]:col-span-4">
                {/* Space reserved for notes if needed in summary */}
              </div>
              
              <div className="@[30rem]:col-span-8">
                <div className="@container">
                  <div className="grid grid-cols-1 @[20rem]:grid-cols-2 @[40rem]:grid-cols-4 gap-3">
                    {/* Agreement Gauge - Only show if available */}
                    {hasAgreementGauge && (
                      <div className="flex flex-col items-center px-2">
                        <div className="w-full min-w-[100px] max-w-[140px] mx-auto">
                          <Gauge
                            value={scoreData.overall_agreement ?? 0}
                            title="Agreement"
                            valueUnit=""
                            min={-1}
                            max={1}
                            decimalPlaces={2}
                            segments={ac1GaugeSegments}
                            showTicks={true}
                          />
                        </div>
                      </div>
                    )}
                    
                    {/* Accuracy Gauge */}
                    {hasAccuracyGauge && (
                      <div className="flex flex-col items-center px-2">
                        <div className="w-full min-w-[100px] max-w-[140px] mx-auto">
                          <Gauge 
                            value={accuracy ?? 0} 
                            title="Accuracy"
                            segments={accuracySegments}
                            showTicks={true}
                          />
                        </div>
                      </div>
                    )}

                    {/* Precision and Recall gauges - only if showPrecisionRecall is true and we have values */}
                    {hasPrecisionGauge && (
                      <div className="flex flex-col items-center px-2">
                        <div className="w-full min-w-[100px] max-w-[140px] mx-auto">
                          <Gauge 
                            value={averagePrecision}
                            title="Precision"
                            segments={accuracySegments}
                            showTicks={true}
                          />
                        </div>
                      </div>
                    )}
                    
                    {hasRecallGauge && (
                      <div className="flex flex-col items-center px-2">
                        <div className="w-full min-w-[100px] max-w-[140px] mx-auto">
                          <Gauge 
                            value={averageRecall}
                            title="Recall"
                            segments={accuracySegments}
                            showTicks={true}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          {/* Raw Agreement Bar */}
          <div className="mt-4">
            <h5 className="text-sm font-medium mb-2">Raw Agreement</h5>
            <RawAgreementBar 
              agreements={scoreData.total_agreements}
              totalItems={scoreData.total_items}
            />
          </div>
        </div>
      )}

      {!hasData && scoreData.scores && scoreData.scores.length === 0 && (
        <div className="py-8 text-center text-muted-foreground">
          <p>No scorecard data available for analysis within the selected parameters.</p>
          <p className="text-sm mt-1">Check that scorecard items exist for the specified parameters.</p>
        </div>
      )}

      {/* Drill-down content (rendered within the card) */}
      {drillDownContent}

      {children}
    </>
  );

  return (
    <ReportBlock
      output={output}
      dateRange={showDateRange ? scoreData.date_range : undefined}
      error={scoreData.error}
      warning={scoreData.warning}
      title={restProps.title || "Scorecard Report"}
      attachedFiles={restProps.attachedFiles}
      log={restProps.log}
      showTitle={showTitle}
      {...restProps}
    >
      {scoreCardContent}
    </ReportBlock>
  );
};

// Set the blockClass property
(ScorecardReport as any).blockClass = 'ScorecardReport';

export default ScorecardReport; 