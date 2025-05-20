import React from 'react';
import { ReportBlockProps } from './ReportBlock';
import ScorecardReport, { ScorecardReportData } from './ScorecardReport';
// No need to import FeedbackItemView since it's used in ScorecardReportEvaluation

// For type-safety, create an interface for the data structure
export interface FeedbackAnalysisData extends ScorecardReportData {
  overall_ac1: number | null;
  date_range: {
    start: string;
    end: string;
  };
}

/**
 * Renders a Feedback Analysis block showing Gwet's AC1 agreement scores.
 * This component displays overall agreement and per-question breakdowns.
 * It extends the base ScorecardReport component.
 * 
 * The confusion matrix now uses FeedbackItemView to display filtered feedback items
 * in a structured before/after format with toggleable raw JSON view.
 */
const FeedbackAnalysis: React.FC<ReportBlockProps> = (props) => {
  // Cast to the expected data type
  const feedbackData = props.output as FeedbackAnalysisData;
  
  if (!feedbackData) {
    return <p>No feedback analysis data available or data is loading.</p>;
  }

  // Create a modified output that maps overall_ac1 to overall_agreement for ScorecardReport
  const modifiedOutput = {
    ...feedbackData,
    overall_agreement: feedbackData.overall_ac1
  };

  return (
    <ScorecardReport 
      {...props}
      output={modifiedOutput}
      title={props.name || 'Feedback Analysis'}
      subtitle="Inter-rater reliability assessment"
      showPrecisionRecall={false} // Don't show precision/recall gauges in feedback analysis
    />
  );
};

// Set the blockClass property
(FeedbackAnalysis as any).blockClass = 'FeedbackAnalysis';

export default FeedbackAnalysis; 