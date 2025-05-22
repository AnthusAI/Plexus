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
  detailsFiles?: string | null;
  className?: string;
  showPrecisionRecall?: boolean;
}

export const ScorecardReportEvaluation: React.FC<ScorecardReportEvaluationProps> = ({ 
  score,
  scoreIndex,
  detailsFiles,
  className,
  showPrecisionRecall = true
}) => {
  const [expanded, setExpanded] = useState(false);
  
  const [scoreDetailsContent, setScoreDetailsContent] = useState<string | null>(null);
  const [isLoadingScoreDetails, setIsLoadingScoreDetails] = useState(false);
  
  const [activeCellFilter, setActiveCellFilter] = useState<{ predicted: string; actual: string } | null>(null);
  const [filteredScoreDetails, setFilteredScoreDetails] = useState<any[] | null>(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [showDetailsSection, setShowDetailsSection] = useState(false);

  const parsedDetailsFiles = useMemo(() => {
    if (typeof detailsFiles === 'string') {
      try {
        return JSON.parse(detailsFiles) as DetailFile[];
      } catch (error) {
        console.error('Failed to parse detailsFiles JSON string in ScorecardReportEvaluation:', error);
        return [];
      }
    }
    return [];
  }, [detailsFiles]);

  const scoreDetailsFileName = `score-${scoreIndex + 1}-results.json`;
  const scoreDetailFile = useMemo(() => {
    return parsedDetailsFiles.find(f => f.name === scoreDetailsFileName);
  }, [parsedDetailsFiles, scoreDetailsFileName]);

  const fetchScoreDetailsContent = useCallback(async () => {
    if (!scoreDetailFile || !scoreDetailFile.path) return;
    
    if (isLoadingScoreDetails || scoreDetailsContent) return;

    setIsLoadingScoreDetails(true);
    try {
      const downloadResult = await downloadData({ path: scoreDetailFile.path }).result;
      const text = await downloadResult.body.text();
      setScoreDetailsContent(text);
    } catch (error) {
      console.error('Error fetching score details content from S3:', error);
      setScoreDetailsContent('Failed to load score details content.');
    } finally {
      setIsLoadingScoreDetails(false);
    }
  }, [scoreDetailFile, isLoadingScoreDetails, scoreDetailsContent]);
  
  useEffect(() => {
    if (activeCellFilter && scoreDetailsContent && typeof scoreDetailsContent === 'string') {
      try {
        const parsedData = JSON.parse(scoreDetailsContent);
        console.debug('Parsed data structure:', 
          Object.keys(parsedData),
          'Looking for:', activeCellFilter.predicted, activeCellFilter.actual);
          
        // Updated to handle the new structure where the keys are directly the predicted/actual values
        // instead of having a 'predicted' wrapper object
        const items = parsedData?.[activeCellFilter.predicted]?.[activeCellFilter.actual];
        
        if (Array.isArray(items)) {
          console.debug(`Found ${items.length} items using predicted[actual] structure`);
          setFilteredScoreDetails(items);
        } else {
          // Try the opposite order in case the data structure is flipped
          const itemsAlt = parsedData?.[activeCellFilter.actual]?.[activeCellFilter.predicted];
          if (Array.isArray(itemsAlt)) {
            console.debug(`Found ${itemsAlt.length} items using actual[predicted] structure`);
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

  const handleConfusionMatrixSelection = (selection: { predicted: string | null; actual: string | null }) => {
    if (selection.predicted && selection.actual) {
      // Store the selected matrix cell values
      console.debug('Selected confusion matrix cell:', selection);
      setActiveCellFilter({ predicted: selection.predicted, actual: selection.actual });
      setShowDetailsSection(true);
      
      // Fetch details if needed and not already loading
      if (!scoreDetailsContent && scoreDetailFile && !isLoadingScoreDetails) {
        fetchScoreDetailsContent();
      }
    } else {
      setActiveCellFilter(null);
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
  const hasVisualizationData = hasClassDistribution || hasPredictedDistribution || (hasConfusionMatrixData && scoreDetailFile);
  
  const hasExtendedData = hasClassDistribution || hasPredictedDistribution || hasDiscussion || hasItems;
  
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
        <div className="flex justify-between items-start mb-4">
          <h3 className="text-base font-medium">{displayName}</h3>
          {hasExtendedData && (
            <CardButton 
              icon={expanded ? ChevronUp : ChevronDown}
              onClick={() => setExpanded(!expanded)}
              aria-label={expanded ? "Collapse details" : "Expand details"}
              className="ml-2"
            />
          )}
        </div>
        
        <div className="@container">
          <div className="grid grid-cols-1 @[30rem]:grid-cols-12 gap-4 items-start">
            <div className="@[30rem]:col-span-4">
              <div className="text-sm space-y-1">
                {itemCount > 0 && (
                  <>
                    <div>
                      <span className="text-muted-foreground">Agreements:</span>{' '}
                      <span>{agreements}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Items:</span>{' '}
                      <span>{itemCount}</span>
                    </div>
                  </>
                )}
              </div>
              
              {hasNotes && (
                <div className="mt-3 text-sm">
                  <p className="text-foreground">{score.notes}</p>
                </div>
              )}
            </div>
            
            <div className="@[30rem]:col-span-8">
              <div className="@container">
                <div className="grid grid-cols-1 @[20rem]:grid-cols-2 @[40rem]:grid-cols-4 gap-3">
                  {score.ac1 !== undefined && (
                    <div className="flex flex-col items-center px-2">
                      <div className="w-full min-w-[100px] max-w-[140px] mx-auto">
                        <Gauge 
                          value={score.ac1 ?? 0} 
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
                  
                  {score.accuracy !== undefined && (
                    <div className="flex flex-col items-center px-2">
                      <div className="w-full min-w-[100px] max-w-[140px] mx-auto">
                        <Gauge 
                          value={score.accuracy ?? 0} 
                          title="Accuracy"
                          segments={accuracySegments}
                          showTicks={true}
                        />
                      </div>
                    </div>
                  )}
                  
                  {showPrecisionRecall && score.precision !== undefined && (
                    <div className="flex flex-col items-center px-2">
                      <div className="w-full min-w-[100px] max-w-[140px] mx-auto">
                        <Gauge 
                          value={score.precision ?? 0} 
                          title="Precision"
                          segments={accuracySegments}
                          showTicks={true}
                        />
                      </div>
                    </div>
                  )}
                  
                  {showPrecisionRecall && score.recall !== undefined && (
                    <div className="flex flex-col items-center px-2">
                      <div className="w-full min-w-[100px] max-w-[140px] mx-auto">
                        <Gauge 
                          value={score.recall ?? 0} 
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
          </div>
        </div>
        
        {hasWarning && (
          <div className="mt-4 bg-red-600 text-white p-3 rounded-sm w-full">
            <div className="flex items-start gap-2">
              <AlertTriangle size={16} className="mt-0.5 flex-shrink-0" />
              <p className="text-sm font-medium">{score.warning}</p>
            </div>
          </div>
        )}

        {hasConfusionMatrixData && scoreDetailFile && (
          <div className="mt-4">
            <ConfusionMatrix 
              data={score.confusion_matrix!}
              onSelectionChange={handleConfusionMatrixSelection} 
            />
          </div>
        )}
      </div>
      
      {showDetailsSection && (
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
      
      {expanded && (
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

// Compatibility alias for backward compatibility
export const ScorecardEvaluation = ScorecardReportEvaluation;

export default ScorecardReportEvaluation; 