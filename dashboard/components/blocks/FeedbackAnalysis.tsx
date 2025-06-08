import React from 'react';
import { ReportBlockProps } from './ReportBlock';
import ScorecardReport, { ScorecardReportData } from './ScorecardReport';
import * as yaml from 'js-yaml';
// No need to import FeedbackItemView since it's used in ScorecardReportEvaluation

// For type-safety, create an interface for the data structure
export interface FeedbackAnalysisData extends ScorecardReportData {
  overall_ac1: number | null;
  date_range: {
    start: string;
    end: string;
  };
  block_title?: string;
  block_description?: string;
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
  if (!props.output) {
    return <p>No feedback analysis data available or data is loading.</p>;
  }

  // Parse YAML if output is string, otherwise use as object (legacy support)
  let feedbackData: FeedbackAnalysisData;
  try {
    if (typeof props.output === 'string') {
      // New format: parse YAML string
      feedbackData = yaml.load(props.output) as FeedbackAnalysisData;
    } else {
      // Legacy format: use object directly
      feedbackData = props.output as FeedbackAnalysisData;
    }
  } catch (error) {
    console.error('❌ FeedbackAnalysis: Failed to parse output data:', error);
    return (
      <div className="p-4 text-center text-destructive">
        Error parsing feedback analysis data. Please check the report generation.
      </div>
    );
  }

  if (!feedbackData) {
    return <p>No feedback analysis data available after parsing.</p>;
  }

  // Create a modified output that maps overall_ac1 to overall_agreement for ScorecardReport
  const modifiedOutput = {
    ...feedbackData,
    overall_agreement: feedbackData.overall_ac1
  };

  // Use a meaningful name, ignoring generic block names
  const title = (props.name && !props.name.startsWith('block_')) ? props.name : 'Feedback Analysis';

  return (
    <ScorecardReport 
      {...props}
      output={{
        ...modifiedOutput,
        // Preserve the original YAML string for the Code button
        rawOutput: typeof props.output === 'string' ? props.output : undefined
      }}
      title={title}
      subtitle={feedbackData.block_description || "Inter-rater reliability assessment"}
      showPrecisionRecall={false} // Don't show precision/recall gauges in feedback analysis
    />
  );
};

// Set the blockClass property
(FeedbackAnalysis as any).blockClass = 'FeedbackAnalysis';

export default FeedbackAnalysis; 