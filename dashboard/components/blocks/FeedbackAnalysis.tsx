import React from 'react';
import { ReportBlockProps } from './ReportBlock';
import { FeedbackAnalysisDisplay, type FeedbackAnalysisDisplayData } from '@/components/ui/feedback-analysis-display';
import * as yaml from 'js-yaml';

// Re-export the interface for backward compatibility
export interface FeedbackAnalysisData extends FeedbackAnalysisDisplayData {}

/**
 * Renders a Feedback Analysis block showing Gwet's AC1 agreement scores.
 * This component displays overall agreement and per-question breakdowns.
 * 
 * This component now uses the reusable FeedbackAnalysisDisplay component
 * to maintain consistency between server-side report blocks and client-side
 * ad-hoc analysis.
 * 
 * The confusion matrix uses FeedbackItemView to display filtered feedback items
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

  // Use a meaningful name, ignoring generic block names
  const title = (props.name && !props.name.startsWith('block_')) ? props.name : 'Feedback Analysis';

  return (
    <FeedbackAnalysisDisplay
      data={feedbackData}
      title={title}
      subtitle={feedbackData.block_description}
      showPrecisionRecall={false} // Don't show precision/recall gauges in feedback analysis
      // Pass through all ReportBlock props for attachments, logs, etc.
      attachedFiles={props.attachedFiles}
      log={props.log}
      rawOutput={typeof props.output === 'string' ? props.output : undefined}
      id={props.id}
      position={props.position}
      config={props.config}
    />
  );
};

// Set the blockClass property
(FeedbackAnalysis as any).blockClass = 'FeedbackAnalysis';

export default FeedbackAnalysis; 