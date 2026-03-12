'use client'

import React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import ClassDistributionVisualizer, { type ClassDistribution } from './ClassDistributionVisualizer'
import PredictedClassDistributionVisualizer from './PredictedClassDistributionVisualizer'
import { ConfusionMatrix, type ConfusionMatrixData } from './confusion-matrix'
import { Gauge, type Segment } from '../components/gauge'
import { GaugeThresholdComputer } from '../utils/gauge-thresholds'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { cn } from '@/lib/utils'

export interface EvaluationCardProps {
  /**
   * Card title
   */
  title: string
  
  /**
   * Optional subtitle displayed below the title
   */
  subtitle?: string
  
  /**
   * Class distribution data for the dataset
   */
  classDistributionData: ClassDistribution[]
  
  /**
   * Whether the class distribution is balanced
   */
  isBalanced?: boolean
  
  /**
   * Optional predicted class distribution data
   */
  predictedClassDistributionData?: ClassDistribution[]
  
  /**
   * Optional confusion matrix data
   */
  confusionMatrixData?: ConfusionMatrixData
  
  /**
   * Accuracy percentage (0-100)
   */
  accuracy: number
  
  /**
   * Gwet AC1 value (0-1)
   */
  gwetAC1?: number
  
  /**
   * Optional custom gauge segments for the accuracy gauge
   * If not provided, segments will be computed from class distribution
   */
  accuracyGaugeSegments?: Segment[]
  
  /**
   * Disables colored segments in the accuracy gauge, showing only a gray background
   * This is useful when we want to show the raw accuracy value without implying interpretability
   */
  disableAccuracySegments?: boolean
  
  /**
   * Optional notes to display at the bottom of the card
   */
  notes?: React.ReactNode
  
  /**
   * Optional warning message to display
   */
  warningMessage?: React.ReactNode
  
  /**
   * Optional CSS class name
   */
  className?: string

  /**
   * Show both AC1 and Accuracy gauges side-by-side
   */
  showBothGauges?: boolean

  /**
   * Layout variant
   * - default: Visualizations span full width, gauges in grid below
   * - oneGauge: Two-column layout with visualizations on left, single gauge on right
   */
  variant?: 'default' | 'oneGauge'
  
  /**
   * Optional additional text to display below the gauge in oneGauge variant
   */
  gaugeDescription?: React.ReactNode
}

/**
 * EvaluationCard Component
 * 
 * A standardized card for displaying model evaluation results with metrics and visualizations
 */
export default function EvaluationCard({
  title,
  subtitle,
  classDistributionData,
  isBalanced = false,
  predictedClassDistributionData,
  confusionMatrixData,
  accuracy,
  gwetAC1,
  accuracyGaugeSegments,
  disableAccuracySegments = false,
  notes,
  warningMessage,
  className,
  showBothGauges = false,
  variant = 'default',
  gaugeDescription
}: EvaluationCardProps) {
  // Compute gauge segments from class distribution if not provided
  const segments = disableAccuracySegments 
    ? [{ start: 0, end: 100, color: 'var(--gauge-inviable)' }]
    : (accuracyGaugeSegments || (() => {
        const distribution: Record<string, number> = {};
        classDistributionData.forEach(item => {
          distribution[item.label] = item.count;
        });
        return GaugeThresholdComputer.createSegments(
          GaugeThresholdComputer.computeThresholds(distribution)
        );
      })());

  // Shared style for gauge titles to ensure consistency
  const gaugeTitleStyle = "text-sm text-muted-foreground text-center min-h-[2.5rem] flex items-center justify-center";

  // Function to render the visualizations in a consistent container
  const renderVisualizations = () => (
    <div className="space-y-4">
      <div>
        <ClassDistributionVisualizer 
          data={classDistributionData} 
          isBalanced={isBalanced} 
        />
      </div>
      
      {confusionMatrixData && (
        <div className="bg-card/50 rounded-md">
          <ConfusionMatrix data={confusionMatrixData} />
        </div>
      )}
      
      {predictedClassDistributionData && (
        <div>
          <PredictedClassDistributionVisualizer 
            data={predictedClassDistributionData}
          />
        </div>
      )}
    </div>
  );

  // OneGauge variant render - two column layout
  if (variant === 'oneGauge') {
    return (
      <Card className={cn("border-none shadow-none bg-card mb-6", className)}>
        <CardContent className="pt-6">
          <h4 className="text-xl font-medium mb-3">{title}</h4>
          {subtitle && (
            <p className="text-sm text-muted-foreground mb-4">
              {subtitle}
            </p>
          )}
          
          <div className="flex flex-col md:flex-row gap-6 items-start">
            {/* Left column: visualizations */}
            <div className="w-full md:w-1/2 overflow-visible">
              {renderVisualizations()}
            </div>
            
            {/* Right column: single gauge */}
            <div className="w-full md:w-1/2 flex flex-col items-center">
              <p className="text-sm text-muted-foreground mb-2 text-center">
                You achieved {accuracy}% accuracy:
              </p>
              <div className="max-w-[270px] mx-auto">
                <Gauge 
                  value={accuracy} 
                  title="Accuracy"
                  segments={segments}
                  showTicks={true}
                />
              </div>
              
              {gaugeDescription && (
                <div className="text-sm mt-6 w-full">
                  {gaugeDescription}
                </div>
              )}
            </div>
          </div>
          
          {/* Notes Section */}
          {notes && (
            <div className="bg-muted/50 rounded-md p-4 mt-6">
              {typeof notes === 'string' ? (
                <>
                  <p className="text-sm font-medium">Key Insight:</p>
                  <p className="text-sm mt-1">{notes}</p>
                </>
              ) : (
                notes
              )}
            </div>
          )}
          
          {/* Warning Message */}
          {warningMessage && (
            <div className="mt-4">
              {typeof warningMessage === 'string' ? (
                <Alert variant="destructive">
                  <AlertTitle>Warning</AlertTitle>
                  <AlertDescription>{warningMessage}</AlertDescription>
                </Alert>
              ) : (
                warningMessage
              )}
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // Default variant render - visualizations full width, gauges below
  return (
    <Card className={cn("border-none shadow-none bg-card mb-6", className)}>
      <CardContent className="pt-3">
        <h4 className="text-xl font-medium mb-3">{title}</h4>
        {subtitle && (
          <p className="text-sm text-muted-foreground mb-4">
            {subtitle}
          </p>
        )}
        
        {/* All visualizations in a single shared container */}
        <div className="mb-6">
          {renderVisualizations()}
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Show both gauges side by side or default behavior */}
          {showBothGauges ? (
            <>
              {/* Agreement (AC1) Gauge */}
              <div className="flex flex-col items-center">
                <div className="max-w-[270px] mx-auto">
                  <Gauge 
                    value={gwetAC1 ?? 0} 
                    title="Agreement"
                    valueUnit=""
                    min={-1}
                    max={1}
                    decimalPlaces={2}
                    showTicks={true}
                    segments={[
                      { start: 0, end: 50, color: 'var(--gauge-inviable)' },      // Negative values (-1 to 0)
                      { start: 50, end: 60, color: 'var(--gauge-converging)' },   // Low alignment (0 to 0.2)
                      { start: 60, end: 75, color: 'var(--gauge-almost)' },       // Moderate alignment (0.2 to 0.5)
                      { start: 75, end: 90, color: 'var(--gauge-viable)' },       // Good alignment (0.5 to 0.8)
                      { start: 90, end: 100, color: 'var(--gauge-great)' }        // Excellent alignment (0.8 to 1.0)
                    ]}
                  />
                </div>
              </div>
              
              {/* Accuracy Gauge */}
              <div className="flex flex-col items-center">
                <div className="max-w-[270px] mx-auto">
                  <Gauge 
                    value={accuracy} 
                    title="Accuracy"
                    showTicks={true}
                    segments={segments}
                  />
                </div>
              </div>
            </>
          ) : (
            <>
              {/* Default behavior with "No context" and "With context" gauges */}
              <div className="flex flex-col items-center">
                <p className={gaugeTitleStyle}>No context for interpretation</p>
                <div className="max-w-[270px] mx-auto">
                  <Gauge
                    value={accuracy}
                    title="Accuracy"
                    showTicks={true}
                    segments={[
                      { start: 0, end: 100, color: 'var(--gauge-inviable)' }
                    ]}
                  />
                </div>
              </div>
              
              {/* Contextual Accuracy Gauge or AC1 Gauge */}
              <div className="flex flex-col items-center">
                <p className={gaugeTitleStyle}>
                  {gwetAC1 !== undefined 
                    ? (gwetAC1 < 0.2 
                      ? 'Poor agreement' 
                      : gwetAC1 < 0.4 
                        ? 'Fair agreement' 
                        : gwetAC1 < 0.6 
                          ? 'Moderate agreement' 
                          : gwetAC1 < 0.8 
                            ? 'Good agreement' 
                            : 'Excellent agreement')
                    : 'With context for interpretation'}
                </p>
                <div className="max-w-[270px] mx-auto">
                  {gwetAC1 !== undefined ? (
                    <Gauge 
                      value={gwetAC1} 
                      title="Agreement"
                      valueUnit=""
                      min={-1}
                      max={1}
                      decimalPlaces={2}
                      showTicks={true}
                      segments={[
                        { start: 0, end: 50, color: 'var(--gauge-inviable)' },      // Negative values (-1 to 0)
                        { start: 50, end: 60, color: 'var(--gauge-converging)' },   // Low alignment (0 to 0.2)
                        { start: 60, end: 75, color: 'var(--gauge-almost)' },       // Moderate alignment (0.2 to 0.5)
                        { start: 75, end: 90, color: 'var(--gauge-viable)' },       // Good alignment (0.5 to 0.8)
                        { start: 90, end: 100, color: 'var(--gauge-great)' }        // Excellent alignment (0.8 to 1.0)
                      ]}
                    />
                  ) : (
                    <Gauge 
                      value={accuracy} 
                      title="Accuracy"
                      segments={segments}
                      showTicks={true}
                    />
                  )}
                </div>
              </div>
            </>
          )}
        </div>
        
        {/* Notes Section */}
        {notes && (
          <div className="bg-muted/50 rounded-md p-4 mt-6">
            {typeof notes === 'string' ? (
              <>
                <p className="text-sm font-medium">Key Insight:</p>
                <p className="text-sm mt-1">{notes}</p>
              </>
            ) : (
              notes
            )}
          </div>
        )}
        
        {/* Warning Message */}
        {warningMessage && (
          <div className="mt-4">
            {typeof warningMessage === 'string' ? (
              <Alert variant="destructive">
                <AlertTitle>Warning</AlertTitle>
                <AlertDescription>{warningMessage}</AlertDescription>
              </Alert>
            ) : (
              warningMessage
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
} 