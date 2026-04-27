/**
 * Ad-hoc Feedback Alignment Component
 * 
 * This component provides on-demand feedback alignment for scorecards and scores.
 * It fetches feedback data client-side, computes analysis metrics, and displays
 * the results using the reusable FeedbackAlignmentDisplay component.
 */

"use client";

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, RefreshCw, Calendar, BarChart3, AlertCircle, MessageCircleMore } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useFeedbackAlignment, type FeedbackAlignmentConfig } from '@/hooks/use-feedback-alignment';
import { FeedbackAlignmentDisplay } from './feedback-alignment-display';
import { useAccount } from '@/app/contexts/AccountContext';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export interface AdHocFeedbackAlignmentProps {
  // Pre-configure the analysis
  scorecardId?: string;
  scoreId?: string;
  scoreIds?: string[];
  scoreName?: string;
  // UI configuration
  title?: string;
  className?: string;
  showHeader?: boolean; // NEW: Control whether to show the header
  // Control whether to show configuration panel
  showConfiguration?: boolean;
  // Default analysis period
  defaultDays?: number;
}

/**
 * Header with period selector and refresh
 */
const AnalysisHeader: React.FC<{
  config: FeedbackAlignmentConfig;
  onConfigChange: (config: FeedbackAlignmentConfig) => void;
  onRefresh: () => void;
  isLoading: boolean;
}> = ({ config, onConfigChange, onRefresh, isLoading }) => {
  const handlePeriodChange = (value: string) => {
    const newConfig = { ...config, days: parseInt(value) };
    onConfigChange(newConfig);
  };

  return (
    <div className="flex items-center gap-2 mb-4">
      <Select
        value={config.days?.toString() || '7'}
        onValueChange={handlePeriodChange}
        disabled={isLoading}
      >
        <SelectTrigger className="w-32">
          <SelectValue placeholder="Select period" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="7">Last 7 days</SelectItem>
          <SelectItem value="14">Last 14 days</SelectItem>
          <SelectItem value="30">Last 30 days</SelectItem>
          <SelectItem value="60">Last 60 days</SelectItem>
          <SelectItem value="90">Last 90 days</SelectItem>
        </SelectContent>
      </Select>
      <Button
        variant="ghost"
        size="icon"
        onClick={onRefresh}
        disabled={isLoading}
        className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
        aria-label="Refresh analysis"
      >
        <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
      </Button>
    </div>
  );
};


/**
 * Main Ad-hoc Feedback Alignment Component
 */
export const AdHocFeedbackAlignment: React.FC<AdHocFeedbackAlignmentProps> = ({
  scorecardId,
  scoreId,
  scoreIds,
  scoreName,
  title,
  className,
  showHeader = true, // Default to true for backward compatibility
  showConfiguration = true,
  defaultDays = 7
}) => {
  const { selectedAccount } = useAccount();
  
  const [config, setConfig] = useState<FeedbackAlignmentConfig>({
    accountId: selectedAccount?.id,
    scorecardId,
    scoreId,
    scoreIds,
    scoreName,
    days: defaultDays
  });

  const { data, isLoading, error, refresh } = useFeedbackAlignment(config);

  // Update accountId when selectedAccount changes
  useEffect(() => {
    if (selectedAccount?.id && selectedAccount.id !== config.accountId) {
      setConfig(prev => ({ ...prev, accountId: selectedAccount.id }));
    }
  }, [selectedAccount?.id, config.accountId]);

  const handleConfigChange = (newConfig: FeedbackAlignmentConfig) => {
    setConfig({ ...newConfig, accountId: selectedAccount?.id });
  };

  const getAnalysisTitle = () => {
    if (title) return title;
    if (scoreId) return 'Score';
    if (scorecardId) return 'Analysis';
    return 'Analysis';
  };

  return (
    <div className={className}>
      {/* Header with Controls */}
      <AnalysisHeader
        config={config}
        onConfigChange={handleConfigChange}
        onRefresh={refresh}
        isLoading={isLoading}
      />

      {/* Error Display */}
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {error}
          </AlertDescription>
        </Alert>
      )}

      {/* Loading State */}
      {isLoading && !data && (
        <Card>
          <CardContent className="flex items-center justify-center py-8">
            <div className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Analyzing feedback data...</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {data && (
        <FeedbackAlignmentDisplay
          data={data}
          title={title}
          showDateRange={true}
          showPrecisionRecall={false}
          showHeader={showHeader}
          className="rounded-lg"
          scorecardId={config.scorecardId}
          scoreId={config.scoreId}
        />
      )}

      {/* Empty State */}
      {!isLoading && !error && !data && (
        <Card>
          <CardContent className="flex items-center justify-center py-8">
            <div className="text-center text-muted-foreground">
              <BarChart3 className="h-8 w-8 mx-auto mb-2" />
              <p>No feedback data found for the selected period</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default AdHocFeedbackAlignment;