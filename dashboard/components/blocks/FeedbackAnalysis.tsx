import React from 'react';
import { ReportBlockProps } from './ReportBlock';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

// For type-safety, create an interface for the data structure
interface QuestionAC1 {
  ac1: number;
  name: string;
  total_comparisons: number;
  mismatches: number;
  mismatch_percentage: number;
}

interface FeedbackAnalysisData {
  overall_ac1: number | null;
  question_ac1s: Record<string, QuestionAC1>;
  total_items: number;
  total_mismatches: number;
  mismatch_percentage: number;
  analysis_date: string;
  scorecard_id: string;
  score_id?: string;
  date_range: {
    start: string;
    end: string;
  };
}

/**
 * Renders a Feedback Analysis block showing Gwet's AC1 agreement scores.
 * This component displays overall agreement and per-question breakdowns.
 */
const FeedbackAnalysis: React.FC<ReportBlockProps> = ({ name, data }) => {
  // Cast to the expected data type
  const feedbackData = data as FeedbackAnalysisData;
  
  if (!feedbackData) {
    return <p>No feedback analysis data available.</p>;
  }

  const hasData = feedbackData.total_items > 0;
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
    return { label: 'Weak', color: 'bg-red-700 text-white' };
  };

  const agreementLevel = getAgreementLevel(feedbackData.overall_ac1);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">
            {name || 'Feedback Analysis'} 
            {feedbackData.score_id && (
              <span className="ml-2 text-sm text-muted-foreground">
                (Score ID: {feedbackData.score_id})
              </span>
            )}
          </h3>
          <div className="flex gap-2 items-center">
            <span className="text-sm text-muted-foreground">
              Overall Agreement:
            </span>
            <Badge className={agreementLevel.color}>
              {hasData 
                ? `${agreementLevel.label} (AC1: ${feedbackData.overall_ac1?.toFixed(4) || 'N/A'})`
                : 'No Data'
              }
            </Badge>
          </div>
        </div>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">Scorecard</p>
                <p className="text-sm">{feedbackData.scorecard_id}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Date Range</p>
                <p className="text-sm">
                  {formattedDate(feedbackData.date_range.start)} to {formattedDate(feedbackData.date_range.end)}
                </p>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Analysis Date</p>
                <p className="text-sm">{formattedDate(feedbackData.analysis_date)}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Items Analyzed</p>
                <p className="text-sm">{feedbackData.total_items}</p>
              </div>
              {hasData && (
                <>
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Total Mismatches</p>
                    <p className="text-sm">{feedbackData.total_mismatches} ({feedbackData.mismatch_percentage.toFixed(1)}%)</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-medium">Agreement (AC1)</p>
                    <p className="text-sm">{feedbackData.overall_ac1?.toFixed(4) || 'N/A'}</p>
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {hasData && Object.keys(feedbackData.question_ac1s).length > 0 && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Question Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Question ID</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="text-right">AC1 Score</TableHead>
                    <TableHead className="text-right">Items</TableHead>
                    <TableHead className="text-right">Mismatches</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(feedbackData.question_ac1s)
                    .sort(([, a], [, b]) => (b.ac1 || 0) - (a.ac1 || 0)) // Sort by AC1 score (descending)
                    .map(([scoreId, question]) => {
                      const level = getAgreementLevel(question.ac1);
                      return (
                        <TableRow key={scoreId}>
                          <TableCell className="font-medium">{scoreId}</TableCell>
                          <TableCell>{question.name}</TableCell>
                          <TableCell className="text-right">
                            <Badge className={level.color}>
                              {question.ac1?.toFixed(4) || 'N/A'}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">{question.total_comparisons}</TableCell>
                          <TableCell className="text-right">
                            {question.mismatches} ({question.mismatch_percentage.toFixed(1)}%)
                          </TableCell>
                        </TableRow>
                      );
                    })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

        {!hasData && (
          <div className="py-8 text-center text-muted-foreground">
            <p>No feedback data available for analysis.</p>
            <p className="text-sm mt-1">Check that feedback items exist for the specified scorecard and date range.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default FeedbackAnalysis; 