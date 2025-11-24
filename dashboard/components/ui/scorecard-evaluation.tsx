"use client";

import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { Badge } from '@/components/ui/badge';
import { ChevronDown, ChevronUp, AlertTriangle, Eye, CheckCircle, XCircle } from 'lucide-react';
import { CardButton } from '@/components/CardButton';
import { Gauge, type Segment } from '@/components/gauge';
import { cn } from '@/lib/utils';
import ClassDistributionVisualizer, { type ClassDistribution } from '@/components/ClassDistributionVisualizer';
import PredictedClassDistributionVisualizer from '@/components/PredictedClassDistributionVisualizer';
import { ConfusionMatrix, type ConfusionMatrixData, type ConfusionMatrixRow } from '@/components/confusion-matrix';
import { GaugeThresholdComputer } from '@/utils/gauge-thresholds';
import { RawAgreementBar } from '@/components/RawAgreementBar';
import { downloadData } from 'aws-amplify/storage';
import { Button } from '@/components/ui/button';
import type { DetailFile } from '../blocks/ReportBlock';
import { FeedbackItemsList, FeedbackItemsView, type FeedbackItem } from '@/components/ui/feedback-item-view';
import { useFeedbackItemsByAnswers, type FeedbackItemWithRelations } from '@/hooks/use-feedback-items-by-answers';

// Export the AC1 gauge segments for reuse in other components
export const ac1GaugeSegments: Segment[] = [
  { start: 0, end: 50, color: 'var(--gauge-inviable)' },      // Negative values (-1 to 0)
  { start: 50, end: 60, color: 'var(--gauge-converging)' },   // Low alignment (0 to 0.2)
  { start: 60, end: 75, color: 'var(--gauge-almost)' },       // Moderate alignment (0.2 to 0.5)
  { start: 75, end: 90, color: 'var(--gauge-viable)' },       // Good alignment (0.5 to 0.8)
  { start: 90, end: 100, color: 'var(--gauge-great)' }        // Excellent alignment (0.8 to 1.0)
];

export interface ScorecardReportEvaluationData {
  id: string;
  question?: string;
  score_name: string;
  cc_question_id?: string;
  ac1?: number | null;
  total_items?: number;
  item_count?: number;
  mismatches?: number;
  accuracy?: number;
  precision?: number;
  recall?: number;
  label_distribution?: Record<string, number>;
  class_distribution?: ClassDistribution[];
  predicted_class_distribution?: ClassDistribution[];
  confusion_matrix?: ConfusionMatrixData;
  warning?: string;
  notes?: string;
  discussion?: string;
  editorName?: string;
  editedAt?: string;
  item?: {
    id: string;
    identifiers?: string;
    externalId?: string;
  };
}

interface ScorecardReportEvaluationProps {
  score: ScorecardReportEvaluationData;
  scoreIndex: number;
  attachedFiles?: string[] | null;
  className?: string;
  showPrecisionRecall?: boolean;
  onCellSelection?: (selection: { predicted: string | null; actual: string | null }) => void;
  // Props for on-demand analysis drill-down
  scorecardId?: string;
  accountId?: string;
  // Prop to determine if this is the only score (for auto-expand behavior)
  isSingleScore?: boolean;
  // Date range for filtering drill-down items
  dateRange?: { start: string; end: string };
}

export const ScorecardReportEvaluation: React.FC<ScorecardReportEvaluationProps> = ({ 
  score,
  scoreIndex,
  attachedFiles,
  className,
  showPrecisionRecall = true,
  onCellSelection,
  scorecardId,
  accountId,
  isSingleScore = false,
  dateRange
}) => {
  const [expanded, setExpanded] = useState(isSingleScore); // Auto-expand if single score
  
  const [scoreDetailsContent, setScoreDetailsContent] = useState<string | null>(null);
  const [isLoadingScoreDetails, setIsLoadingScoreDetails] = useState(false);
  
  const [activeCellFilter, setActiveCellFilter] = useState<{ predicted: string; actual: string } | null>(null);
  const [filteredScoreDetails, setFilteredScoreDetails] = useState<any[] | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [showDetailsSection, setShowDetailsSection] = useState(false);
  
  // State for on-demand feedback analysis drill-down
  const [onDemandItems, setOnDemandItems] = useState<FeedbackItemWithRelations[]>([]);
  const [showOnDemandDetails, setShowOnDemandDetails] = useState(false);
  
  // Hook for fetching feedback items by answers
  const { fetchFeedbackItems, loading: fetchingItems, error: fetchError } = useFeedbackItemsByAnswers();

  const parsedAttachedFiles = useMemo(() => {
    if (Array.isArray(attachedFiles)) {
      // If it's already an array of storage paths or DetailFile objects
      return attachedFiles.map((file: string | DetailFile) => {
        if (typeof file === 'string') {
          // Treat as Amplify storage path - extract filename from path
          const fileName = file.split('/').pop() || file;
          return {
            name: fileName,
            path: file // This is the Amplify storage path
          } as DetailFile;
        }
        return file as DetailFile;
      }).filter(Boolean) as DetailFile[];
    } else if (typeof attachedFiles === 'string') {
      // Could be a single path or a JSON string of paths
      try {
        const parsed = JSON.parse(attachedFiles);
        if (Array.isArray(parsed)) {
          return parsed.map((file: string | DetailFile) => {
            if (typeof file === 'string') {
              const fileName = file.split('/').pop() || file;
              return {
                name: fileName,
                path: file
              } as DetailFile;
            }
            return file as DetailFile;
          });
        }
      } catch (error) {
        // Not JSON, treat as single storage path
        const fileName = (attachedFiles as string).split('/').pop() || (attachedFiles as string);
        return [{
          name: fileName,
          path: attachedFiles as string
        }] as DetailFile[];
      }
    }
    return [];
  }, [attachedFiles]);

  const scoreDetailsFileName = `score-${scoreIndex + 1}-results.json`;
  const scoreDetailsFile = useMemo(() => {
    // First try to find in parsedAttachedFiles
    let file = parsedAttachedFiles.find(f => f.name === scoreDetailsFileName);
    
    // If not found and score has indexed_items_file, create a file entry
    if (!file && (score as any).indexed_items_file) {
      const indexedFile = (score as any).indexed_items_file;
      file = {
        name: indexedFile,
        path: indexedFile // The backend should provide the full path
      };
    }
    
    return file;
  }, [parsedAttachedFiles, scoreDetailsFileName, score]);

  const fetchScoreDetailsContent = useCallback(async () => {
    if (!scoreDetailsFile || !scoreDetailsFile.path) return;
    
    if (isLoadingScoreDetails || scoreDetailsContent) return;

    setIsLoadingScoreDetails(true);
    try {
      // Determine which storage bucket to use based on file path
      let storageOptions: { path: string; options?: { bucket?: string } } = { path: scoreDetailsFile.path };
      
      if (scoreDetailsFile.path.startsWith('reportblocks/')) {
        // Report block files are stored in the reportBlockDetails bucket
        storageOptions = {
          path: scoreDetailsFile.path,
          options: { bucket: 'reportBlockDetails' }
        };
      } else if (scoreDetailsFile.path.startsWith('scoreresults/')) {
        // Score result files are stored in the scoreResultAttachments bucket
        storageOptions = {
          path: scoreDetailsFile.path,
          options: { bucket: 'scoreResultAttachments' }
        };
      }
      
      const downloadResult = await downloadData(storageOptions).result;
      const text = await downloadResult.body.text();
      setScoreDetailsContent(text);
    } catch (error) {
      console.error('Error fetching score details content from S3:', error);
      setScoreDetailsContent('Failed to load score details content.');
    } finally {
      setIsLoadingScoreDetails(false);
    }
  }, [scoreDetailsFile, isLoadingScoreDetails, scoreDetailsContent]);
  
  useEffect(() => {
    if (activeCellFilter && scoreDetailsContent && typeof scoreDetailsContent === 'string') {
      try {
        const parsedData = JSON.parse(scoreDetailsContent);
          
        // Updated to handle the new structure where the keys are directly the predicted/actual values
        // instead of having a 'predicted' wrapper object
        const items = parsedData?.[activeCellFilter.predicted]?.[activeCellFilter.actual];
        
        if (Array.isArray(items)) {
          setFilteredScoreDetails(items);
        } else {
          // Try the opposite order in case the data structure is flipped
          const itemsAlt = parsedData?.[activeCellFilter.actual]?.[activeCellFilter.predicted];
          if (Array.isArray(itemsAlt)) {
            setFilteredScoreDetails(itemsAlt);
          } else {
            setFilteredScoreDetails([]); 
            console.warn('Could not find items for filter. Structure of parsed data:', 
              JSON.stringify(parsedData, null, 2).substring(0, 200) + '...');
          }
        }
      } catch (error) {
        console.error('Failed to parse or filter score details content:', error);
        setFilteredScoreDetails([]); 
      }
    } else {
      setFilteredScoreDetails(null);
    }
  }, [activeCellFilter, scoreDetailsContent]);

  const handleConfusionMatrixSelection = async (selection: { predicted: string | null; actual: string | null }) => {
    if (selection.predicted && selection.actual) {
      // Store the selected matrix cell values
      
      // For ReportBlock usage (when scoreDetailsFile exists), show details section
      if (scoreDetailsFile) {
        setActiveCellFilter({ predicted: selection.predicted, actual: selection.actual });
        setShowDetailsSection(true);
        
        if (!scoreDetailsContent && !isLoadingScoreDetails) {
          fetchScoreDetailsContent();
        }
      }
      // For on-demand analysis (when scorecardId and accountId are provided), fetch feedback items
      else if (scorecardId && accountId && score.id) {
        const filter = {
          accountId: accountId,
          scorecardId: scorecardId,
          scoreId: score.id,
          predicted: selection.predicted,
          actual: selection.actual,
          // Include date range if provided
          startDate: dateRange?.start ? new Date(dateRange.start) : undefined,
          endDate: dateRange?.end ? new Date(dateRange.end) : undefined
        };
        
        setActiveCellFilter({ predicted: selection.predicted, actual: selection.actual });
        setShowOnDemandDetails(true);
        
        try {
          const items = await fetchFeedbackItems(filter);
          setOnDemandItems(items);
        } catch (error) {
          console.error('❌ Error fetching feedback items:', error);
          setOnDemandItems([]);
        }
      }
      
    } else {
      setActiveCellFilter(null);
      if (scoreDetailsFile) {
        setShowDetailsSection(false);
      } else {
        setShowOnDemandDetails(false);
        setOnDemandItems([]);
      }
    }
    
    // Always call the external callback if provided (for both ReportBlock and on-demand usage)
    onCellSelection?.(selection);
  };
  
  const getAgreementLevel = (ac1: number | null): { label: string; color: string } => {
    if (ac1 === null) return { label: 'No Data', color: 'bg-muted text-muted-foreground' };
    if (ac1 >= 0.8) return { label: 'Strong', color: 'bg-green-700 text-white' };
    if (ac1 >= 0.6) return { label: 'Moderate', color: 'bg-yellow-600 text-white' };
    if (ac1 >= 0.4) return { label: 'Fair', color: 'bg-orange-500 text-white' }; 
    if (ac1 >= 0.0) return { label: 'Slight', color: 'bg-red-400 text-white' };
    return { label: 'Poor', color: 'bg-red-700 text-white' };
  };

  const level = score.ac1 !== undefined ? getAgreementLevel(score.ac1) : { label: 'N/A', color: 'bg-muted text-muted-foreground' };
  const displayName = score.score_name || score.question || 'Unnamed Score';
  const itemCount = score.total_items || score.item_count || 0;
  const mismatches = score.mismatches || 0;
  const agreements = itemCount - mismatches;
  const agreementPercent = itemCount > 0 ? (agreements / itemCount) * 100 : 0;
  const hasWarning = !!score.warning;
  const hasNotes = !!score.notes;
  const hasDiscussion = !!score.discussion;
  const hasItems = itemCount > 0;
  
  const accuracySegments: Segment[] = score.label_distribution 
    ? GaugeThresholdComputer.createSegments(
        GaugeThresholdComputer.computeThresholds(score.label_distribution)
      )
    : [{ start: 0, end: 100, color: 'var(--gauge-inviable)' }];
  
  const hasClassDistribution = score.class_distribution && score.class_distribution.length > 0;
  const hasPredictedDistribution = score.predicted_class_distribution && score.predicted_class_distribution.length > 0;
  const hasConfusionMatrixData = score.confusion_matrix && score.confusion_matrix.matrix && score.confusion_matrix.labels && score.confusion_matrix.matrix.length > 0;
  const hasVisualizationData = hasClassDistribution || hasPredictedDistribution || hasConfusionMatrixData;
  
  const hasExtendedData = hasClassDistribution || hasPredictedDistribution || hasConfusionMatrixData || hasDiscussion || hasItems;
  
  const parsedIdentifiers = useMemo(() => {
    if (score.item?.identifiers) {
      try {
        return JSON.parse(score.item.identifiers) as Array<{
          name: string;
          id: string;
          url?: string;
        }>;
      } catch (error) {
        console.error('Failed to parse identifiers JSON string:', error);
        return [];
      }
    }
    return [];
  }, [score.item?.identifiers]);
  
  // Format date to a more readable format
  const formatDate = (dateString?: string) => {
    if (!dateString) return '';
    try {
      const date = new Date(dateString);
      return date.toLocaleString();
    } catch (e) {
      return dateString;
    }
  };

  return (
    <div className={cn(
      "transition-all bg-card rounded-lg relative min-w-[280px]",
      className
    )}>
      <div className="p-4">
        <div className="mb-4">
          <h3 className="text-base font-medium">{displayName}</h3>
        </div>
        
        <div className="@container">
          <div className="relative">
            {/* Warning - always in left column */}
            {hasWarning && (
              <div className="@[30rem]:w-1/3 @[30rem]:float-left mb-3">
                <div className="bg-false text-foreground p-3 rounded-sm">
                  <div className="flex items-start gap-2">
                    <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
                    <p className="text-sm font-medium">{score.warning}</p>
                  </div>
                </div>
              </div>
            )}
            
            {/* Gauges - floated to the right */}
            <div className="@[30rem]:float-right @[30rem]:w-2/3 @[30rem]:pl-4">
              <div className="@container">
                <div className="grid grid-cols-1 @[20rem]:grid-cols-2 @[40rem]:grid-cols-4 gap-3">
                  {score.ac1 !== undefined && score.ac1 !== null && (
                    <div className="flex flex-col items-center px-2">
                      <div style={{ width: '200px' }}>
                        <Gauge 
                          value={score.ac1} 
                          title="Agreement"
                          valueUnit=""
                          min={-1}
                          max={1}
                          decimalPlaces={2}
                          segments={ac1GaugeSegments}
                          showTicks={true}
                        />
                      </div>
                    </div>
                  )}
                  
                  {score.ac1 === null && (
                    <div className="flex flex-col items-center px-2">
                      <div style={{ width: '200px' }}>
                        <Gauge 
                          title="Agreement"
                          valueUnit=""
                          min={-1}
                          max={1}
                          decimalPlaces={2}
                          segments={ac1GaugeSegments}
                          showTicks={true}
                        />
                      </div>
                    </div>
                  )}
                  
                  {score.accuracy !== undefined && score.accuracy !== null && (
                    <div className="flex flex-col items-center px-2">
                      <div style={{ width: '200px' }}>
                        <Gauge 
                          value={score.accuracy} 
                          title="Accuracy"
                          segments={accuracySegments}
                          showTicks={true}
                        />
                      </div>
                    </div>
                  )}
                  
                  {score.accuracy === null && (
                    <div className="flex flex-col items-center px-2">
                      <div style={{ width: '200px' }}>
                        <Gauge 
                          title="Accuracy"
                          segments={accuracySegments}
                          showTicks={true}
                        />
                      </div>
                    </div>
                  )}
                  
                  {showPrecisionRecall && score.precision !== undefined && score.precision !== null && (
                    <div className="flex flex-col items-center px-2">
                      <div style={{ width: '200px' }}>
                        <Gauge 
                          value={score.precision} 
                          title="Precision"
                          segments={accuracySegments}
                          showTicks={true}
                        />
                      </div>
                    </div>
                  )}
                  
                  {showPrecisionRecall && score.precision === null && (
                    <div className="flex flex-col items-center px-2">
                      <div style={{ width: '200px' }}>
                        <Gauge 
                          title="Precision"
                          segments={accuracySegments}
                          showTicks={true}
                        />
                      </div>
                    </div>
                  )}
                  
                  {showPrecisionRecall && score.recall !== undefined && score.recall !== null && (
                    <div className="flex flex-col items-center px-2">
                      <div style={{ width: '200px' }}>
                        <Gauge 
                          value={score.recall} 
                          title="Recall"
                          segments={accuracySegments}
                          showTicks={true}
                        />
                      </div>
                    </div>
                  )}
                  
                  {showPrecisionRecall && score.recall === null && (
                    <div className="flex flex-col items-center px-2">
                      <div style={{ width: '200px' }}>
                        <Gauge 
                          title="Recall"
                          segments={accuracySegments}
                          showTicks={true}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            {/* Notes - start under warning, flow around gauges */}
            {hasNotes && (
              <div className={cn(
                "text-sm",
                hasWarning ? "clear-left @[30rem]:clear-none" : ""
              )}>
                <p className="text-foreground">{score.notes}</p>
              </div>
            )}
            
            {/* Clear floats */}
            <div className="clear-both"></div>
          </div>
        </div>

        {hasConfusionMatrixData && (
          <div className="mt-4">
            <ConfusionMatrix 
              data={score.confusion_matrix!}
              onSelectionChange={(scoreDetailsFile || onCellSelection || (scorecardId && accountId)) ? handleConfusionMatrixSelection : () => {}} 
            />
          </div>
        )}

        {/* Centered expand/collapse UI - hide for single scores */}
        {hasExtendedData && !isSingleScore && (
          <div className="mt-4 flex flex-col items-center">
            <div className="w-full h-px bg-border mb-1"></div>
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center justify-center rounded-full hover:bg-muted/50 transition-colors"
              aria-label={expanded ? "Collapse details" : "Expand details"}
            >
              {expanded ? (
                <ChevronUp className="h-3 w-3 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-3 w-3 text-muted-foreground" />
              )}
            </button>
          </div>
        )}
      </div>
      
      {showDetailsSection && scoreDetailsFile && (
        <div className="px-4 pb-4">
          <FeedbackItemsView
            items={filteredScoreDetails as FeedbackItem[] || []}
            showRawJson={showRawJson}
            onToggleView={() => setShowRawJson(!showRawJson)}
            isLoading={isLoadingScoreDetails}
            filterInfo={activeCellFilter && filteredScoreDetails ? {
              predicted: activeCellFilter.predicted,
              actual: activeCellFilter.actual,
              count: filteredScoreDetails.length
            } : undefined}
            onClose={() => {
              setShowDetailsSection(false);
              setActiveCellFilter(null);
            }}
          />
        </div>
      )}
      
      {showOnDemandDetails && !scoreDetailsFile && (
        <div className="px-4 pb-4">
          <FeedbackItemsView
            items={onDemandItems}
            showRawJson={showRawJson}
            onToggleView={() => setShowRawJson(!showRawJson)}
            isLoading={fetchingItems}
            filterInfo={activeCellFilter ? {
              predicted: activeCellFilter.predicted,
              actual: activeCellFilter.actual,
              count: onDemandItems.length
            } : undefined}
            onClose={() => {
              setShowOnDemandDetails(false);
              setActiveCellFilter(null);
              setOnDemandItems([]);
            }}
          />
          
          {fetchError && (
            <div className="mt-2 p-2 bg-red-100 text-red-800 rounded text-sm">
              Error fetching feedback items: {fetchError}
            </div>
          )}
        </div>
      )}
      
      {(expanded || isSingleScore) && (
        <div className="px-4 pb-4">
          {(hasClassDistribution || hasPredictedDistribution) && (
            <div className="space-y-6 mb-4">
              {hasClassDistribution && (
                  <div>
                  <h5 className="text-sm font-medium mb-2">Class Distribution</h5>
                  <ClassDistributionVisualizer 
                      data={score.class_distribution!} 
                      isBalanced={false} 
                  />
                  </div>
              )}
              {hasPredictedDistribution && (
                  <div>
                  <h5 className="text-sm font-medium mb-2">Predicted Class Distribution</h5>
                  <PredictedClassDistributionVisualizer 
                      data={score.predicted_class_distribution!}
                  />
                  </div>
              )}
            </div>
          )}
          {hasItems && (
            <div className="mt-0">
              <h5 className="text-sm font-medium mb-2">Raw Agreement</h5>
              <RawAgreementBar 
                agreements={agreements}
                totalItems={itemCount}
              />
            </div>
          )}
          {hasDiscussion && (
            <div className="mt-6">
              <div className="text-sm prose-sm max-w-none">
                <p>{score.discussion}</p>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Editor information and identifiers */}
      {(score.editorName || parsedIdentifiers.length > 0) && (
        <div className="px-4 pb-4 mt-4 pt-4 border-t border-border">
          <div className="flex flex-col md:flex-row justify-between gap-4">
            {/* Editor information on the left */}
            <div className="space-y-1">
              {score.editorName && (
                <>
                  <div className="text-sm">
                    <span className="font-medium">Edited by:</span> {score.editorName}
                  </div>
                  {score.editedAt && (
                    <div className="text-xs text-muted-foreground">
                      {formatDate(score.editedAt)}
                    </div>
                  )}
                </>
              )}
            </div>
            
            {/* Identifiers on the right */}
            {parsedIdentifiers.length > 0 && (
              <div className="w-full md:w-auto">
                <h6 className="text-xs text-muted-foreground mb-1">Identifiers</h6>
                <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                  {parsedIdentifiers.map((identifier, index) => (
                    <React.Fragment key={`${identifier.name}-${index}`}>
                      <div className="text-muted-foreground">{identifier.name}:</div>
                      <div className="text-muted-foreground">
                        {identifier.url ? (
                          <a 
                            href={identifier.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline"
                            title={identifier.id}
                          >
                            {identifier.id.length > 10 
                              ? `${identifier.id.substring(0, 10)}...` 
                              : identifier.id}
                          </a>
                        ) : (
                          <span title={identifier.id}>
                            {identifier.id.length > 10 
                              ? `${identifier.id.substring(0, 10)}...` 
                              : identifier.id}
                          </span>
                        )}
                      </div>
                    </React.Fragment>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// Convenience alias
export const ScorecardEvaluation = ScorecardReportEvaluation;
export type ScorecardEvaluationData = ScorecardReportEvaluationData;
export type ScorecardEvaluationProps = ScorecardReportEvaluationProps;

export default ScorecardReportEvaluation; 