/**
 * Reusable Feedback Analysis Display Component
 * 
 * This component displays feedback analysis results and can be used with both
 * server-side generated data (from report blocks) and client-side generated data
 * (from ad-hoc analysis).
 */

"use client";

import React, { useCallback } from 'react';
import ScorecardReport, { type ScorecardReportData } from '@/components/blocks/ScorecardReport';
import type { ReportBlockProps } from '@/components/blocks/ReportBlock';
// Removed unused imports - individual scores handle their own drill-down now
import { useAccount } from '@/app/contexts/AccountContext';

export interface FeedbackAnalysisDisplayData extends ScorecardReportData {
  overall_ac1: number | null;
  date_range: {
    start: string;
    end: string;
  };
  block_title?: string;
  block_description?: string;
}

export interface FeedbackAnalysisDisplayProps {
  data: FeedbackAnalysisDisplayData;
  title?: string;
  subtitle?: string;
  showDateRange?: boolean;
  showPrecisionRecall?: boolean;
  showHeader?: boolean; // NEW: Control whether to show the header at all
  hideSummary?: boolean; // NEW: Control whether to hide the summary section
  className?: string;
  onCellSelection?: (selection: { predicted: string | null; actual: string | null }) => void;
  // ReportBlock-specific props for server-side usage
  attachedFiles?: string[] | null;
  log?: string;
  rawOutput?: string;
  id?: string;
  position?: number;
  config?: Record<string, any>;
  // On-demand analysis props - needed for GSI queries
  scorecardId?: string;
  scoreId?: string;
}

/**
 * Renders a Feedback Analysis display showing Gwet's AC1 agreement scores.
 * This component displays overall agreement and per-question breakdowns.
 * 
 * The confusion matrix uses interactive cells to allow drilling down into
 * specific feedback items in a structured before/after format.
 */
export const FeedbackAnalysisDisplay: React.FC<FeedbackAnalysisDisplayProps> = ({
  data,
  title,
  subtitle,
  showDateRange = true,
  showPrecisionRecall = false,
  showHeader = true, // Default to true for backward compatibility
  hideSummary = false, // Default to false to maintain existing behavior
  className,
  onCellSelection,
  // ReportBlock-specific props
  attachedFiles,
  log,
  rawOutput,
  id = 'feedback-analysis-display',
  position = 0,
  config = { class: 'FeedbackAnalysis' },
  // On-demand analysis props
  scorecardId,
  scoreId
}) => {
  // Helper function to filter out unwanted default subtitle text
  const filterSubtitle = (text: string | undefined): string | undefined => {
    if (!text) return undefined;
    const unwantedTexts = [
      "Inter-rater reliability assessment",
      "Inter-rater Reliability Assessment"
    ];
    return unwantedTexts.includes(text) ? undefined : text;
  };

  // Removed scorecard-level drill-down state - individual scores handle their own now
  
  // Get account context for accountId
  const { selectedAccount } = useAccount();

  // Handle confusion matrix cell selection for on-demand analysis
  const handleOnDemandCellSelection = useCallback(async (selection: { predicted: string | null; actual: string | null }) => {
    console.debug('🎯 Confusion matrix cell clicked:', selection);
    console.debug('🔍 Cell selection context:', { 
      hasAttachedFiles: !!attachedFiles, 
      hasSelectedAccount: !!selectedAccount,
      scorecardId, 
      scoreId 
    });
    
    // Call the external callback if provided (for ReportBlock usage)
    onCellSelection?.(selection);
    
    // For scorecard analysis, individual scores now handle their own drill-down
    // No need to handle it at the scorecard level anymore
    console.debug('🔄 Drill-down handled by individual score components');
  }, [onCellSelection]);

  if (!data) {
    return <p>No feedback analysis data available or data is loading.</p>;
  }

  // Create a modified output that maps overall_ac1 to overall_agreement for ScorecardReport
  const modifiedOutput: ScorecardReportData = {
    ...data,
    overall_agreement: data.overall_ac1,
    // Include rawOutput for the Code button functionality
    rawOutput: rawOutput
  };

  // Create ReportBlockProps to satisfy ScorecardReport interface
  const reportBlockProps: ReportBlockProps = {
    id: id,
    name: showHeader ? (title || 'Feedback Analysis') : undefined,
    type: 'FeedbackAnalysis',
    position: position,
    output: modifiedOutput,
    config: config,
    title: showHeader ? title : undefined,
    subtitle: showHeader ? filterSubtitle(subtitle) : filterSubtitle(data.block_description),
    attachedFiles: attachedFiles,
    log: log
  };

  return (
    <div className={className}>
      <ScorecardReport 
        {...reportBlockProps}
        showDateRange={showDateRange}
        showPrecisionRecall={showPrecisionRecall}
        onCellSelection={handleOnDemandCellSelection}
        showTitle={showHeader}
        hideSummary={hideSummary}
        scorecardId={scorecardId}
        accountId={selectedAccount?.id}
        // No drill-down content at scorecard level - individual scores handle their own
      />
    </div>
  );
};

export default FeedbackAnalysisDisplay;