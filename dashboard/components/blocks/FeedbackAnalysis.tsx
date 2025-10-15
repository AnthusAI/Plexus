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

  // Check if this is "all scorecards" mode
  if ((feedbackData as any).mode === 'all_scorecards') {
    const allScorecardsData = feedbackData as any;
    const scorecards = allScorecardsData.scorecards || [];

    // State to track which scorecard is currently expanded
    const [expandedScorecardId, setExpandedScorecardId] = React.useState<string | null>(null);

    return (
      <div className="space-y-8">
        {/* Summary header */}
        <div className="p-4 bg-muted/30 rounded-lg">
          <h3 className="text-lg font-semibold mb-2">{title}</h3>
          {allScorecardsData.block_description && (
            <p className="text-sm text-muted-foreground mb-2">{allScorecardsData.block_description}</p>
          )}
          <div className="text-sm space-y-1">
            <p><strong>Total scorecards analyzed:</strong> {allScorecardsData.total_scorecards_analyzed || scorecards.length}</p>
            {allScorecardsData.total_scorecards_filtered !== undefined && allScorecardsData.total_scorecards_filtered > 0 && (
              <p><strong>Scorecards filtered (no data):</strong> {allScorecardsData.total_scorecards_filtered}</p>
            )}
            {allScorecardsData.date_range && (
              <p><strong>Date range:</strong> {new Date(allScorecardsData.date_range.start).toLocaleDateString()} - {new Date(allScorecardsData.date_range.end).toLocaleDateString()}</p>
            )}
          </div>
        </div>

        {/* Render each scorecard with collapsible details */}
        {scorecards.length === 0 ? (
          <p className="text-muted-foreground">No scorecards found.</p>
        ) : (
          <div className="space-y-2">
            {scorecards.map((scorecardData: any, index: number) => {
              const scorecardId = scorecardData.scorecard_id || index.toString();
              const isExpanded = expandedScorecardId === scorecardId;

              return (
                <div key={scorecardId} className="border rounded-lg">
                  {/* Collapsed summary view */}
                  <button
                    onClick={() => setExpandedScorecardId(isExpanded ? null : scorecardId)}
                    className="w-full px-4 py-3 flex items-center justify-between hover:bg-muted/30 transition-colors text-left"
                  >
                    <div className="flex-1 flex items-center gap-4">
                      <span className="text-sm text-muted-foreground font-mono">#{scorecardData.rank || index + 1}</span>
                      <span className="font-semibold">{scorecardData.scorecard_name || scorecardData.scorecard_id}</span>
                      <div className="flex gap-4 text-sm">
                        <span className="text-muted-foreground">
                          AC1: <span className="font-medium text-foreground">{scorecardData.overall_ac1?.toFixed(3) || 'N/A'}</span>
                        </span>
                        <span className="text-muted-foreground">
                          Items: <span className="font-medium text-foreground">{scorecardData.total_items || 0}</span>
                        </span>
                        <span className="text-muted-foreground">
                          Accuracy: <span className="font-medium text-foreground">{scorecardData.accuracy ? `${scorecardData.accuracy.toFixed(1)}%` : 'N/A'}</span>
                        </span>
                      </div>
                    </div>
                    <svg
                      className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {/* Expanded detailed view - only rendered when expanded */}
                  {isExpanded && (
                    <div className="px-4 py-4 border-t">
                      <FeedbackAnalysisDisplay
                        data={scorecardData}
                        showHeader={false}
                        showDateRange={false}
                        showPrecisionRecall={false}
                        attachedFiles={props.attachedFiles}
                        log={props.log}
                        rawOutput={typeof props.output === 'string' ? props.output : undefined}
                        id={`${props.id}-${index}`}
                        position={props.position}
                        config={props.config}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // Single scorecard mode
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