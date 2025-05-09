import React from 'react';
import { ReportBlockProps } from './ReportBlock';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Gauge, Segment } from '@/components/gauge';

// For type-safety, create an interface for the data structure
interface ScoreData {
  id: string;
  score_name: string;
  cc_question_id: string;
  ac1: number | null;
  item_count: number;
  mismatches: number;
  mismatch_percentage?: number;
  accuracy?: number;
}

interface FeedbackAnalysisData {
  overall_ac1: number | null;
  scores: ScoreData[];
  total_items: number;
  total_mismatches: number;
  mismatch_percentage?: number;
  accuracy?: number;
  date_range: {
    start: string;
    end: string;
  };
}

// Define AC1 segments (percentages of the -1 to 1 range)
const ac1GaugeSegments: Segment[] = [
  { start: 0, end: 50, color: 'var(--gauge-inviable)' },   // AC1: -1.0 to 0.0
  { start: 50, end: 70, color: 'var(--gauge-converging)' }, // AC1: 0.0 to 0.4
  { start: 70, end: 80, color: 'var(--gauge-almost)' },    // AC1: 0.4 to 0.6
  { start: 80, end: 90, color: 'var(--gauge-viable)' },    // AC1: 0.6 to 0.8
  { start: 90, end: 100, color: 'var(--gauge-great)' },   // AC1: 0.8 to 1.0
];

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

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h3 className="text-xl font-semibold">
          {name || 'Feedback Analysis'} 
        </h3>
      </div>

      {/* Score Cards Section */}
      {hasData && feedbackData.scores.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {feedbackData.scores
            .sort((a, b) => (b.ac1 === null ? -2 : b.ac1) - (a.ac1 === null ? -2 : a.ac1))
            .map((score) => {
              const agreements = score.item_count - score.mismatches;
              return (
                <Card key={score.id} className="bg-card shadow-none border-none">
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
                            valueFormatter={(v) => v.toFixed(3)}
                            showTicks={false}
                        />
                    </div>
                    <div className="w-full sm:w-1/2 max-w-[200px] sm:max-w-none">
                        <Gauge
                            title="Accuracy"
                            value={score.accuracy ?? undefined}
                            showTicks={false}
                        />
                    </div>
                  </CardContent>
                </Card>
              );
            })}
        </div>
      )}

      {/* Summary Card - Conditionally Rendered */}
      {showSummary && (
        <Card className="bg-card shadow-none border-none">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">Date Range</p>
                <p className="text-sm">
                  {formattedDate(feedbackData.date_range.start)} to {formattedDate(feedbackData.date_range.end)}
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Items Analyzed</p>
                <p className="text-sm">{feedbackData.total_items}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Total Mismatches</p>
                <p className="text-sm">
                  {feedbackData.total_mismatches} (
                  {feedbackData.accuracy !== undefined 
                    ? (100 - feedbackData.accuracy).toFixed(1) 
                    : feedbackData.mismatch_percentage !== undefined
                      ? feedbackData.mismatch_percentage.toFixed(1)
                      : "0.0"}%)
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Accuracy</p>
                <p className="text-sm">
                  {feedbackData.accuracy !== undefined 
                    ? feedbackData.accuracy.toFixed(1) 
                    : feedbackData.mismatch_percentage !== undefined
                      ? (100 - feedbackData.mismatch_percentage).toFixed(1)
                      : "100.0"}%
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Overall Agreement (AC1)</p>
                {(feedbackData.overall_ac1 !== null && feedbackData.overall_ac1 !== undefined) ? (
                  (() => {
                    const level = getAgreementLevel(feedbackData.overall_ac1);
                    return (
                      <Badge className={level.color}>
                        {`${level.label} (AC1: ${feedbackData.overall_ac1.toFixed(4)})`}
                      </Badge>
                    );
                  })()
                ) : (
                  <Badge className="bg-muted text-muted-foreground">No Data</Badge>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
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