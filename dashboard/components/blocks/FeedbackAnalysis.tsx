import React from 'react';
import { ReportBlockProps } from './ReportBlock';
import { FeedbackAnalysisDisplay, type FeedbackAnalysisDisplayData } from '@/components/ui/feedback-analysis-display';
import * as yaml from 'js-yaml';
import { Gauge, type Segment } from '@/components/gauge';
import { GaugeThresholdComputer } from '@/utils/gauge-thresholds';
import { ac1GaugeSegments } from '@/components/ui/scorecard-evaluation';
import { RawAgreementBar } from '@/components/RawAgreementBar';
import { ChevronUp, ChevronDown } from 'lucide-react';

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
          <div>
            {scorecards.map((scorecardData: any, index: number) => {
              const scorecardId = scorecardData.scorecard_id || index.toString();
              const isExpanded = expandedScorecardId === scorecardId;

              // Calculate accuracy segments if label distribution is available
              const accuracySegments: Segment[] = scorecardData.label_distribution 
                ? GaugeThresholdComputer.createSegments(
                    GaugeThresholdComputer.computeThresholds(scorecardData.label_distribution)
                  )
                : [{ start: 0, end: 100, color: 'var(--gauge-inviable)' }];

              // Calculate accuracy value  
              const accuracy = scorecardData.accuracy !== undefined 
                ? scorecardData.accuracy 
                : scorecardData.mismatch_percentage !== undefined
                  ? (100 - scorecardData.mismatch_percentage)
                  : scorecardData.total_items > 0
                    ? (scorecardData.total_agreements / scorecardData.total_items) * 100
                    : 100.0;

              return (
                <div key={scorecardId} style={{ marginBottom: (index < scorecards.length - 1 && !isExpanded) ? '2em' : '0' }}>
                  {/* Scorecard card */}
                  <div className="bg-card rounded-lg">
                    <div className="px-4 py-4">
                      <div className="flex items-start justify-between gap-4 mb-4">
                        {/* Left side: Rank, name, and items count */}
                        <div className="flex items-start gap-4 flex-1">
                          <span className="text-sm text-muted-foreground font-mono pt-1">#{scorecardData.rank || index + 1}</span>
                          <div className="flex-1">
                            <div className="font-semibold mb-1">{scorecardData.scorecard_name || scorecardData.scorecard_id}</div>
                            <div className="text-sm text-muted-foreground">
                              Items: <span className="font-medium text-foreground">{scorecardData.total_items || 0}</span>
                            </div>
                          </div>
                        </div>

                        {/* Right side: Larger gauges */}
                        <div className="flex items-center gap-6">
                          <div className="flex flex-col items-center" style={{ width: '200px' }}>
                            <Gauge
                              value={scorecardData.overall_ac1 ?? 0}
                              title="Agreement"
                              valueUnit=""
                              min={-1}
                              max={1}
                              decimalPlaces={2}
                              segments={ac1GaugeSegments}
                              showTicks={true}
                            />
                          </div>
                          <div className="flex flex-col items-center" style={{ width: '200px' }}>
                            <Gauge 
                              value={accuracy ?? 0} 
                              title="Accuracy"
                              segments={accuracySegments}
                              showTicks={true}
                            />
                          </div>
                        </div>
                      </div>

                      {/* Raw Agreement Bar */}
                      <div className="mb-4">
                        <h5 className="text-sm font-medium mb-2">Raw Agreement</h5>
                        <RawAgreementBar 
                          agreements={scorecardData.total_agreements || 0}
                          totalItems={scorecardData.total_items || 0}
                        />
                      </div>

                      {/* Expand/Collapse button - matching individual score pattern */}
                      <div className="flex flex-col items-center mt-4">
                        <div className="w-full h-px bg-border mb-1"></div>
                        <button
                          onClick={() => setExpandedScorecardId(isExpanded ? null : scorecardId)}
                          className="flex items-center justify-center rounded-full hover:bg-muted/50 transition-colors"
                          aria-label={isExpanded ? "Collapse details" : "Expand details"}
                        >
                          {isExpanded ? (
                            <ChevronUp className="h-3 w-3 text-muted-foreground" />
                          ) : (
                            <ChevronDown className="h-3 w-3 text-muted-foreground" />
                          )}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Expanded detailed view - rendered below the card when expanded */}
                  {isExpanded && (
                    <div className="pt-3" style={{ marginBottom: index < scorecards.length - 1 ? '4em' : '0' }}>
                      <FeedbackAnalysisDisplay
                        data={scorecardData}
                        showHeader={false}
                        showDateRange={false}
                        showPrecisionRecall={false}
                        hideSummary={true}
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