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
export interface FeedbackAnalysisData extends FeedbackAnalysisDisplayData {
  memories_file?: string;
  memories?: {
    scores: Array<{
      score_name: string;
      score_id: string;
      topics: Array<{
        topic_id: number;
        label: string;
        keywords: string[];
        exemplars: Array<{ text: string; item_id?: string | null; identifiers?: Record<string, string> | null }>;
        member_count: number;
        memory_weight: number;
        memory_tier: "hot" | "warm" | "cold";
        lifecycle_tier: string;
        cause?: string;
        is_new: boolean;
        is_trending: boolean;
      }>;
    }>;
  };
}

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
// Sub-component for an expanded scorecard in all-scorecards mode.
// Fetches the scorecard's memories file and merges topics into score rows,
// matching single-scorecard mode behaviour so memories appear inline per-score.
const ExpandedScorecardView: React.FC<{
  scorecardData: any;
  blockProps: ReportBlockProps;
  index: number;
  totalCount: number;
}> = ({ scorecardData, blockProps, index, totalCount }) => {
  const [loadedMemories, setLoadedMemories] = React.useState<FeedbackAnalysisData['memories'] | null>(null);

  const memoriesFile: string | null = scorecardData.memories_file ?? null;
  React.useEffect(() => {
    if (!memoriesFile || loadedMemories) return;
    (async () => {
      try {
        const { downloadData } = await import('aws-amplify/storage');
        const result = await downloadData({
          path: memoriesFile,
          options: { bucket: 'reportBlockDetails' as any },
        }).result;
        const text = await result.body.text();
        const parsed = yaml.load(text) as FeedbackAnalysisData['memories'];
        setLoadedMemories(parsed ?? null);
      } catch (e) {
        console.warn('ExpandedScorecardView: failed to load memories_file', e);
      }
    })();
  }, [memoriesFile, loadedMemories]);

  const memories = loadedMemories ?? scorecardData.memories ?? null;
  const memoriesByScoreId = memories
    ? Object.fromEntries(memories.scores.map((s: any) => [s.score_id, s.topics]))
    : {};
  const dataWithTopics = memories ? {
    ...scorecardData,
    scores: scorecardData.scores?.map((s: any) => ({
      ...s,
      topics: memoriesByScoreId[s.score_id] ?? s.topics,
    })),
  } : scorecardData;

  return (
    <div className="pt-3" style={{ marginBottom: index < totalCount - 1 ? '4em' : '0' }}>
      <FeedbackAnalysisDisplay
        data={dataWithTopics}
        showHeader={false}
        showDateRange={false}
        showPrecisionRecall={false}
        hideSummary={true}
        attachedFiles={blockProps.attachedFiles}
        log={blockProps.log}
        rawOutput={typeof blockProps.output === 'string' ? blockProps.output : undefined}
        id={`${blockProps.id}-${index}`}
        position={blockProps.position}
        config={blockProps.config}
      />
    </div>
  );
};

// Sub-component for "all scorecards" mode — keeps hooks at top level
const AllScorecardsView: React.FC<{
  data: any;
  title: string;
  blockProps: ReportBlockProps;
}> = ({ data, title, blockProps }) => {
  const scorecards = data.scorecards || [];
  const [expandedScorecardId, setExpandedScorecardId] = React.useState<string | null>(null);

  return (
    <div className="space-y-8">
      <div className="p-4 bg-muted/30 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{title}</h3>
        {data.block_description && (
          <p className="text-sm text-muted-foreground mb-2">{data.block_description}</p>
        )}
        <div className="text-sm space-y-1">
          <p><strong>Total scorecards analyzed:</strong> {data.total_scorecards_analyzed || scorecards.length}</p>
          {data.total_scorecards_filtered !== undefined && data.total_scorecards_filtered > 0 && (
            <p><strong>Scorecards filtered (no data):</strong> {data.total_scorecards_filtered}</p>
          )}
          {data.date_range && (
            <p><strong>Date range:</strong> {new Date(data.date_range.start).toLocaleDateString()} - {new Date(data.date_range.end).toLocaleDateString()}</p>
          )}
        </div>
      </div>

      {scorecards.length === 0 ? (
        <p className="text-muted-foreground">No scorecards found.</p>
      ) : (
        <div>
          {scorecards.map((scorecardData: any, index: number) => {
            const scorecardId = scorecardData.scorecard_id || index.toString();
            const isExpanded = expandedScorecardId === scorecardId;

            const accuracySegments: Segment[] = scorecardData.label_distribution
              ? GaugeThresholdComputer.createSegments(
                  GaugeThresholdComputer.computeThresholds(scorecardData.label_distribution)
                )
              : [{ start: 0, end: 100, color: 'var(--gauge-inviable)' }];

            const accuracy = scorecardData.accuracy !== undefined
              ? scorecardData.accuracy
              : scorecardData.mismatch_percentage !== undefined
                ? (100 - scorecardData.mismatch_percentage)
                : scorecardData.total_items > 0
                  ? (scorecardData.total_agreements / scorecardData.total_items) * 100
                  : 100.0;

            return (
              <div key={scorecardId} style={{ marginBottom: (index < scorecards.length - 1 && !isExpanded) ? '2em' : '0' }}>
                <div className="bg-card rounded-lg">
                  <div className="px-4 py-4">
                    <div className="flex items-start justify-between gap-4 mb-4">
                      <div className="flex items-start gap-4 flex-1">
                        <span className="text-sm text-muted-foreground font-mono pt-1">#{scorecardData.rank || index + 1}</span>
                        <div className="flex-1">
                          <div className="font-semibold mb-1">{scorecardData.scorecard_name || scorecardData.scorecard_id}</div>
                          <div className="text-sm text-muted-foreground">
                            Items: <span className="font-medium text-foreground">{scorecardData.total_items || 0}</span>
                          </div>
                        </div>
                      </div>
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
                    <div className="mb-4">
                      <h5 className="text-sm font-medium mb-2">Raw Agreement</h5>
                      <RawAgreementBar
                        agreements={scorecardData.total_agreements || 0}
                        totalItems={scorecardData.total_items || 0}
                      />
                    </div>
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
                {isExpanded && (
                  <ExpandedScorecardView
                    scorecardData={scorecardData}
                    blockProps={blockProps}
                    index={index}
                    totalCount={scorecards.length}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

const FeedbackAnalysis: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<FeedbackAnalysisData | null>(null);
  const [loadedMemories, setLoadedMemories] = React.useState<FeedbackAnalysisData['memories'] | null>(null);
  const [expandedScorecardId, setExpandedScorecardId] = React.useState<string | null>(null);
  const [expandedMemoryIds, setExpandedMemoryIds] = React.useState<Set<string>>(new Set());
  const toggleMemory = React.useCallback((id: string) => {
    setExpandedMemoryIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  // Parse output unconditionally so hooks always run in the same order
  let parsedOutput: FeedbackAnalysisData | null = null;
  let parseError = false;
  if (props.output) {
    try {
      if (typeof props.output === 'string') {
        parsedOutput = yaml.load(props.output) as FeedbackAnalysisData;
      } else {
        parsedOutput = props.output as FeedbackAnalysisData;
      }
    } catch (error) {
      console.error('❌ FeedbackAnalysis: Failed to parse output data:', error);
      parseError = true;
    }
  }

  // Fetch compacted output attachment if present (large outputs are offloaded to S3)
  const outputAttachment = (parsedOutput as any)?.output_attachment ?? null;
  const outputCompacted = (parsedOutput as any)?.output_compacted ?? false;
  React.useEffect(() => {
    if (!outputCompacted || !outputAttachment || loadedOutput) return;
    (async () => {
      try {
        const { downloadData } = await import('aws-amplify/storage');
        const result = await downloadData({
          path: outputAttachment,
          options: { bucket: 'reportBlockDetails' as any },
        }).result;
        const text = await result.body.text();
        setLoadedOutput(yaml.load(text) as FeedbackAnalysisData);
      } catch (e) {
        console.warn('FeedbackAnalysis: failed to load output attachment', e);
      }
    })();
  }, [outputCompacted, outputAttachment, loadedOutput]);

  // Use loaded attachment data if available, otherwise fall back to inline parsed output
  const feedbackData = loadedOutput ?? parsedOutput;

  const memoriesFile = feedbackData?.memories_file ?? null;
  React.useEffect(() => {
    if (!memoriesFile || loadedMemories) return;
    (async () => {
      try {
        const { downloadData } = await import('aws-amplify/storage');
        const result = await downloadData({
          path: memoriesFile,
          options: { bucket: 'reportBlockDetails' as any },
        }).result;
        const text = await result.body.text();
        const parsed = yaml.load(text) as FeedbackAnalysisData['memories'];
        setLoadedMemories(parsed ?? null);
      } catch (e) {
        console.warn('FeedbackAnalysis: failed to load memories_file', e);
      }
    })();
  }, [memoriesFile, loadedMemories]);

  if (!props.output) {
    return <p>No feedback analysis data available or data is loading.</p>;
  }
  if (parseError) {
    return (
      <div className="p-4 text-center text-destructive">
        Error parsing feedback analysis data. Please check the report generation.
      </div>
    );
  }

  // Show loading state while fetching compacted output
  if (outputCompacted && !loadedOutput) {
    return <p className="text-sm text-muted-foreground p-4">Loading report data…</p>;
  }

  if (!feedbackData) {
    return <p>No feedback analysis data available after parsing.</p>;
  }

  // Use a meaningful name, ignoring generic block names
  const title = (props.name && !props.name.startsWith('block_')) ? props.name : 'Feedback Analysis';

  // Check if this is "all scorecards" mode
  if ((feedbackData as any).mode === 'all_scorecards') {
    return (
      <FeedbackAnalysisDisplay
        data={{ scores: [] } as any}
        title={title}
        subtitle={(feedbackData as any).block_description}
        showPrecisionRecall={false}
        showHeader={false}
        hideSummary={true}
        attachedFiles={props.attachedFiles}
        log={props.log}
        rawOutput={typeof props.output === 'string' ? props.output : undefined}
        id={props.id}
        position={props.position}
        config={props.config}
      >
        <AllScorecardsView data={feedbackData as any} title={title} blockProps={props} />
      </FeedbackAnalysisDisplay>
    );
  }

  // Single scorecard mode — merge memory topics into each score entry
  const singleMemories = loadedMemories ?? feedbackData.memories;
  const memoriesByScoreId = singleMemories
    ? Object.fromEntries(singleMemories.scores.map(s => [s.score_id, s.topics]))
    : {};
  const feedbackDataWithTopics = singleMemories ? {
    ...feedbackData,
    scores: feedbackData.scores?.map((s: any) => ({
      ...s,
      topics: memoriesByScoreId[s.score_id] ?? s.topics,
    })),
  } : feedbackData;

  return (
    <div>
      <FeedbackAnalysisDisplay
        data={feedbackDataWithTopics as any}
        title={title}
        subtitle={feedbackData.block_description}
        showPrecisionRecall={false}
        attachedFiles={props.attachedFiles}
        log={props.log}
        rawOutput={typeof props.output === 'string' ? props.output : undefined}
        id={props.id}
        position={props.position}
        config={props.config}
      />
    </div>
  );
};

// Set the blockClass property
(FeedbackAnalysis as any).blockClass = 'FeedbackAnalysis';

export default FeedbackAnalysis; 
