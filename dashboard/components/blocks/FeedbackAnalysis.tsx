import React from 'react';
import { ReportBlockProps } from './ReportBlock';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GaugeThresholdComputer } from '@/utils/gauge-thresholds';
import { FeedbackAnalysisEvaluation, FeedbackAnalysisEvaluationData } from '@/components/ui/feedback-analysis-evaluation';
import { RawAgreementBar } from '@/components/RawAgreementBar';
import { Gauge, type Segment } from '@/components/gauge';

// For type-safety, create an interface for the data structure
interface FeedbackAnalysisData {
  overall_ac1: number | null;
  scores: FeedbackAnalysisEvaluationData[];
  total_items: number;
  total_mismatches: number;
  mismatch_percentage?: number;
  accuracy?: number;
  date_range: {
    start: string;
    end: string;
  };
  label_distribution?: Record<string, number>;
}

/**
 * Renders a Feedback Analysis block showing Gwet's AC1 agreement scores.
 * This component displays overall agreement and per-question breakdowns.
 */
const FeedbackAnalysis: React.FC<ReportBlockProps> = ({ name, output }) => {
  // Cast to the expected data type
  const feedbackData = output as FeedbackAnalysisData;
  
  if (!feedbackData) {
    // It might be better to render a specific loading/empty state component
    // or return a more structured empty block representation.
    return <p>No feedback analysis data available or data is loading.</p>;
  }

  const hasData = feedbackData.scores && feedbackData.scores.length > 0;
  const showSummary = hasData && feedbackData.scores.length > 1;

  const formattedDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString();
    } catch (e) {
      return dateStr;
    }
  };

  const getAgreementLevel = (ac1: number | null): { label: string; color: string } => {
    if (ac1 === null) return { label: 'No Data', color: 'bg-muted text-muted-foreground' };
    if (ac1 >= 0.8) return { label: 'Strong', color: 'bg-green-700 text-white' };
    if (ac1 >= 0.6) return { label: 'Moderate', color: 'bg-yellow-600 text-white' };
    if (ac1 >= 0.4) return { label: 'Fair', color: 'bg-orange-500 text-white' }; 
    if (ac1 >= 0.0) return { label: 'Slight', color: 'bg-red-400 text-white' };
    return { label: 'Poor', color: 'bg-red-700 text-white' };
  };

  // Calculate accuracy segments if label distribution is available
  const accuracySegments: Segment[] = feedbackData.label_distribution 
    ? GaugeThresholdComputer.createSegments(
        GaugeThresholdComputer.computeThresholds(feedbackData.label_distribution)
      )
    : [{ start: 0, end: 100, color: 'var(--gauge-inviable)' }];

  // Calculate accuracy value  
  const accuracy = feedbackData.accuracy !== undefined 
    ? feedbackData.accuracy 
    : feedbackData.mismatch_percentage !== undefined
      ? (100 - feedbackData.mismatch_percentage)
      : 100.0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h3 className="text-xl font-semibold">
          {name || 'Feedback Analysis'} 
        </h3>
      </div>

      {/* Score Cards Section */}
      {hasData && feedbackData.scores.length > 0 && (
        <div className="space-y-4">
          {feedbackData.scores
            .sort((a, b) => (b.ac1 === null ? -2 : b.ac1) - (a.ac1 === null ? -2 : a.ac1))
            .map((score, index) => (
              <FeedbackAnalysisEvaluation 
                key={score.id || `score-${index}`} 
                score={score} 
              />
            ))}
        </div>
      )}

      {/* Summary Card - Conditionally Rendered with flat styling */}
      {showSummary && (
        <div className="bg-card rounded-lg p-4">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-base font-medium">Summary</h3>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-start">
            {/* Left side - metadata */}
            <div className="md:col-span-5">
              <div className="text-sm space-y-1">
                <div>
                  <span className="text-muted-foreground">Agreements:</span>{' '}
                  <span>{feedbackData.total_items - feedbackData.total_mismatches}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Items:</span>{' '}
                  <span>{feedbackData.total_items}</span>
                </div>
                <div className="mt-3">
                  <span className="text-muted-foreground">Date Range:</span>{' '}
                  <span>{formattedDate(feedbackData.date_range.start)} to {formattedDate(feedbackData.date_range.end)}</span>
                </div>
              </div>
            </div>
            
            {/* Right side - Gauges */}
            <div className="md:col-span-7">
              <div className="grid grid-cols-2 gap-4">
                {/* AC1 Gauge */}
                <div className="flex flex-col items-center">
                  <div className="w-full max-w-[160px] mx-auto">
                    <Gauge 
                      value={feedbackData.overall_ac1 ?? 0} 
                      title="Agreement (AC1)"
                      valueUnit=""
                      min={-1}
                      max={1}
                      decimalPlaces={2}
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
                  <div className="w-full max-w-[160px] mx-auto">
                    <Gauge 
                      value={accuracy} 
                      title="Accuracy"
                      segments={accuracySegments}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          {/* Raw Agreement Bar */}
          <div className="mt-4">
            <h5 className="text-sm font-medium mb-2">Raw Agreement</h5>
            <RawAgreementBar 
              agreements={feedbackData.total_items - feedbackData.total_mismatches}
              totalItems={feedbackData.total_items}
            />
          </div>
        </div>
      )}

      {!hasData && feedbackData.scores && feedbackData.scores.length === 0 && (
        <div className="py-8 text-center text-muted-foreground">
          <p>No feedback data available for analysis within the selected parameters.</p>
          <p className="text-sm mt-1">Check that feedback items exist for the specified scorecard and date range.</p>
        </div>
      )}
    </div>
  );
};

export default FeedbackAnalysis; 