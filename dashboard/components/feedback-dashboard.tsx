"use client";

import React, { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import {
  ArrowLeft,
  BarChart3,
  CalendarDays,
  ChevronRight,
  FilePlus2,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

import { useAccount } from "@/app/contexts/AccountContext";
import ScorecardContext from "@/components/ScorecardContext";
import { useFeedbackVolume } from "@/hooks/use-feedback-volume";
import { useIncrementalRows } from "@/components/blocks/useIncrementalRows";
import { ChartContainer } from "@/components/ui/chart";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { createTask } from "@/utils/data-operations";
import {
  buildFeedbackReportCommand,
  getFeedbackReportActions,
  type FeedbackReportActionDefinition,
} from "@/utils/feedback-report-actions";
import {
  createDateWindowFromDateInputs,
  type FeedbackVolumePoint,
  type FeedbackVolumeSeries,
} from "@/utils/feedback-volume";

const VOLUME_CHART_CONFIG = {
  unchanged: {
    label: "Unchanged",
    color: "var(--true)",
  },
  changed: {
    label: "Changed",
    color: "var(--false)",
  },
  invalid: {
    label: "Invalid / Unclassified",
    color: "var(--progress-background)",
  },
};

const PRESET_OPTIONS = [
  { value: "14", label: "14d" },
  { value: "30", label: "30d" },
  { value: "90", label: "90d" },
  { value: "180", label: "180d" },
  { value: "365", label: "365d" },
  { value: "custom", label: "Custom" },
] as const;

type PresetValue = (typeof PRESET_OPTIONS)[number]["value"];

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatWindowLabel(start: string, end: string): string {
  return `${new Date(start).toLocaleDateString()} - ${new Date(new Date(end).getTime() - 1).toLocaleDateString()}`;
}

function FeedbackVolumeTooltip({ active, payload }: any) {
  if (!active || !payload?.length) {
    return null;
  }

  const point = payload[0]?.payload as FeedbackVolumePoint | undefined;
  if (!point) {
    return null;
  }

  return (
    <div className="rounded-md border bg-background p-3 text-xs shadow-lg">
      <div className="font-medium">{point.label}</div>
      <div className="mb-2 text-muted-foreground">
        {new Date(point.start).toLocaleString()} - {new Date(point.end).toLocaleString()}
      </div>
      <div>Total: {formatNumber(point.feedback_items_total)}</div>
      <div>Unchanged: {formatNumber(point.feedback_items_unchanged)}</div>
      <div>Changed: {formatNumber(point.feedback_items_changed)}</div>
      <div>Invalid / Unclassified: {formatNumber(point.feedback_items_invalid_or_unclassified)}</div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: number;
  detail?: string;
}) {
  return (
    <Card className="border-border/60">
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold">{formatNumber(value)}</div>
        {detail ? <div className="mt-1 text-xs text-muted-foreground">{detail}</div> : null}
      </CardContent>
    </Card>
  );
}

function FeedbackVolumeChart({
  points,
  compact = false,
}: {
  points: FeedbackVolumePoint[];
  compact?: boolean;
}) {
  const data = points.map((point) => ({
    ...point,
    unchanged: point.feedback_items_unchanged,
    changed: point.feedback_items_changed,
    invalid: point.feedback_items_invalid_or_unclassified,
  }));

  return (
    <ChartContainer
      config={VOLUME_CHART_CONFIG}
      className={compact ? "h-[88px] w-full" : "h-[280px] w-full"}
    >
      <BarChart data={data} margin={{ left: compact ? 0 : 8, right: compact ? 0 : 8, top: 8, bottom: 8 }}>
        {!compact ? <CartesianGrid vertical={false} strokeDasharray="3 3" /> : null}
        <XAxis
          dataKey="label"
          hide={compact}
          tickLine={false}
          axisLine={false}
          minTickGap={18}
        />
        <YAxis
          hide={compact}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <Tooltip content={<FeedbackVolumeTooltip />} />
        <Bar dataKey="unchanged" stackId="feedback" fill="var(--true)" isAnimationActive={false} />
        <Bar dataKey="changed" stackId="feedback" fill="var(--false)" isAnimationActive={false} />
        <Bar dataKey="invalid" stackId="feedback" fill="var(--progress-background)" isAnimationActive={false} />
      </BarChart>
    </ChartContainer>
  );
}

function LoadingDashboardState() {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Card key={index} className="border-border/60">
            <CardHeader className="pb-2">
              <div className="h-4 w-24 animate-pulse rounded bg-muted" />
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="h-8 w-20 animate-pulse rounded bg-muted" />
              <div className="h-3 w-32 animate-pulse rounded bg-muted" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card className="border-border/60">
        <CardHeader>
          <div className="h-5 w-40 animate-pulse rounded bg-muted" />
          <div className="h-4 w-56 animate-pulse rounded bg-muted" />
        </CardHeader>
        <CardContent>
          <div className="h-[280px] animate-pulse rounded-lg bg-muted" />
        </CardContent>
      </Card>
    </div>
  );
}

function EmptyScopeCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <Card className="border-dashed border-border/60">
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
    </Card>
  );
}

function FeedbackWindowControls({
  preset,
  setPreset,
  customStartDate,
  setCustomStartDate,
  customEndDate,
  setCustomEndDate,
}: {
  preset: PresetValue;
  setPreset: (value: PresetValue) => void;
  customStartDate: string;
  setCustomStartDate: (value: string) => void;
  customEndDate: string;
  setCustomEndDate: (value: string) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {PRESET_OPTIONS.map((option) => (
          <Button
            key={option.value}
            type="button"
            variant={preset === option.value ? "default" : "outline"}
            size="sm"
            onClick={() => setPreset(option.value)}
            className="rounded-full"
          >
            {option.label}
          </Button>
        ))}
      </div>
      {preset === "custom" ? (
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-card px-3 py-2">
            <CalendarDays className="h-4 w-4 text-muted-foreground" />
            <Input
              type="date"
              value={customStartDate}
              onChange={(event) => setCustomStartDate(event.target.value)}
              className="h-8 w-[150px] border-0 bg-transparent px-0 shadow-none"
            />
          </div>
          <span className="text-sm text-muted-foreground">to</span>
          <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-card px-3 py-2">
            <CalendarDays className="h-4 w-4 text-muted-foreground" />
            <Input
              type="date"
              value={customEndDate}
              onChange={(event) => setCustomEndDate(event.target.value)}
              className="h-8 w-[150px] border-0 bg-transparent px-0 shadow-none"
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function VolumeOverviewCard({
  title,
  description,
  points,
  summary,
  bucketLabel,
}: {
  title: string;
  description: string;
  points: FeedbackVolumePoint[];
  summary: {
    feedback_items_total: number;
    feedback_items_changed: number;
    feedback_items_unchanged: number;
    feedback_items_invalid_or_unclassified: number;
    feedback_items_valid: number;
  };
  bucketLabel: string;
}) {
  return (
    <Card className="border-border/60">
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Total Feedback Items"
            value={summary.feedback_items_total}
            detail={`Buckets: ${bucketLabel}`}
          />
          <MetricCard label="Changed" value={summary.feedback_items_changed} />
          <MetricCard label="Unchanged" value={summary.feedback_items_unchanged} />
          <MetricCard
            label="Invalid / Unclassified"
            value={summary.feedback_items_invalid_or_unclassified}
            detail={`Valid feedback: ${formatNumber(summary.feedback_items_valid)}`}
          />
        </div>
        <FeedbackVolumeChart points={points} />
      </CardContent>
    </Card>
  );
}

function SeriesCard({
  series,
  onSelect,
  reportActions,
}: {
  series: FeedbackVolumeSeries;
  onSelect?: () => void;
  reportActions?: React.ReactNode;
}) {
  const hasFeedback = series.summary.feedback_items_total > 0;

  return (
    <Card className="border-border/60">
      <CardHeader className="gap-2 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1">
          <CardTitle className="text-base">{series.label}</CardTitle>
          <CardDescription>
            {hasFeedback
              ? `${formatNumber(series.summary.feedback_items_total)} feedback items in the selected window`
              : "No feedback in the selected window"}
          </CardDescription>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {reportActions}
          {onSelect ? (
            <Button variant="outline" size="sm" onClick={onSelect}>
              Open
              <ChevronRight className="h-4 w-4" />
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Total" value={series.summary.feedback_items_total} />
          <MetricCard label="Changed" value={series.summary.feedback_items_changed} />
          <MetricCard label="Unchanged" value={series.summary.feedback_items_unchanged} />
          <MetricCard label="Invalid / Unclassified" value={series.summary.feedback_items_invalid_or_unclassified} />
        </div>
        {hasFeedback ? (
          <FeedbackVolumeChart points={series.points} compact />
        ) : (
          <div className="rounded-lg bg-muted/40 px-3 py-4 text-sm text-muted-foreground">
            This scope has no collected feedback for the selected date window.
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FeedbackReportActionsMenu({
  scorecardId,
  scoreId,
  days,
  startDate,
  endDate,
  timezone,
  weekStart,
  buttonLabel = "Generate report",
}: {
  scorecardId: string;
  scoreId?: string | null;
  days?: number;
  startDate?: string | null;
  endDate?: string | null;
  timezone: string;
  weekStart: "monday" | "sunday";
  buttonLabel?: string;
}) {
  const router = useRouter();
  const { selectedAccount } = useAccount();
  const [isDispatching, setIsDispatching] = useState(false);
  const actions = getFeedbackReportActions(Boolean(scoreId));

  const dispatchReport = async (action: FeedbackReportActionDefinition) => {
    if (!selectedAccount?.id) {
      toast.error("No account is selected.");
      return;
    }

    try {
      setIsDispatching(true);
      const command = buildFeedbackReportCommand({
        actionId: action.id,
        scorecardId,
        scoreId,
        days,
        startDate,
        endDate,
        timezone,
        weekStart,
      });

      const task = await createTask({
        type: "feedback report",
        target: "report",
        command,
        accountId: selectedAccount.id,
        dispatchStatus: "PENDING",
        status: "PENDING",
      });

      if (!task?.id) {
        toast.error("Failed to queue report generation.");
        return;
      }

      toast.success(`${action.label} queued`, {
        description: (
          <span className="block max-w-[28rem] truncate font-mono text-xs">
            {command}
          </span>
        ),
        action: {
          label: "View task",
          onClick: () => router.push(`/lab/tasks/${task.id}`),
        },
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to queue report generation.");
    } finally {
      setIsDispatching(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" disabled={isDispatching}>
          {isDispatching ? <Loader2 className="h-4 w-4 animate-spin" /> : <FilePlus2 className="h-4 w-4" />}
          {buttonLabel}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        {actions.map((action) => (
          <DropdownMenuItem
            key={action.id}
            onSelect={() => {
              void dispatchReport(action);
            }}
          >
            {action.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default function FeedbackDashboard() {
  const { selectedAccount, isLoadingAccounts } = useAccount();
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null);
  const [selectedScore, setSelectedScore] = useState<string | null>(null);
  const [preset, setPreset] = useState<PresetValue>("90");
  const [customStartDate, setCustomStartDate] = useState("");
  const [customEndDate, setCustomEndDate] = useState("");

  const browserTimezone = useMemo(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    []
  );

  const customWindow = useMemo(() => {
    if (preset !== "custom" || !customStartDate || !customEndDate) {
      return null;
    }
    try {
      return createDateWindowFromDateInputs(customStartDate, customEndDate, browserTimezone);
    } catch {
      return null;
    }
  }, [browserTimezone, customEndDate, customStartDate, preset]);

  const hookConfig = useMemo(() => {
    if (preset === "custom") {
      return {
        startDate: customWindow?.start,
        endDate: customWindow?.end,
      };
    }
    return {
      days: Number(preset),
    };
  }, [customWindow, preset]);

  const { data, isLoading, error } = useFeedbackVolume({
    accountId: selectedAccount?.id,
    scorecardId: selectedScorecard,
    scoreId: selectedScore,
    timezone: browserTimezone,
    weekStart: "monday",
    ...hookConfig,
  });

  const visibleScoreSeries = useIncrementalRows(data?.scoreSeries || [], {
    initialCount: 8,
    pageSize: 8,
  });

  const currentWindowLabel = data?.dateRange.label
    || (preset === "custom" && customWindow
      ? formatWindowLabel(customWindow.start.toISOString(), customWindow.end.toISOString())
      : `Last ${preset} days`);

  const timelineLabel = data?.bucketPolicy.bucket_type || "calendar_week";
  const canDispatchScopedReports = Boolean(selectedScorecard && data);

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 p-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-muted-foreground">
              <BarChart3 className="h-4 w-4" />
              <span className="text-sm">Live feedback volume</span>
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Feedback</h1>
              <p className="text-sm text-muted-foreground">
                Front-end feedback volume analytics with scorecard drilldown and direct report dispatch.
              </p>
            </div>
          </div>
          {canDispatchScopedReports ? (
            <FeedbackReportActionsMenu
              scorecardId={selectedScorecard!}
              scoreId={selectedScore}
              days={preset === "custom" ? undefined : Number(preset)}
              startDate={preset === "custom" ? customStartDate : undefined}
              endDate={preset === "custom" ? customEndDate : undefined}
              timezone={browserTimezone}
              weekStart="monday"
            />
          ) : null}
        </div>

        <Card className="border-border/60">
          <CardContent className="flex flex-col gap-4 pt-6 xl:flex-row xl:items-start xl:justify-between">
            <div className="flex-1">
              <ScorecardContext
                selectedScorecard={selectedScorecard}
                setSelectedScorecard={setSelectedScorecard}
                selectedScore={selectedScore}
                setSelectedScore={setSelectedScore}
              />
            </div>
            <FeedbackWindowControls
              preset={preset}
              setPreset={setPreset}
              customStartDate={customStartDate}
              setCustomStartDate={setCustomStartDate}
              customEndDate={customEndDate}
              setCustomEndDate={setCustomEndDate}
            />
          </CardContent>
        </Card>

        {selectedScore ? (
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelectedScore(null)}>
              <ArrowLeft className="h-4 w-4" />
              Back to scorecard
            </Button>
            <div className="text-sm text-muted-foreground">
              Viewing {data?.score?.name || selectedScore}
            </div>
          </div>
        ) : null}

        {isLoadingAccounts ? (
          <LoadingDashboardState />
        ) : !selectedAccount ? (
          <EmptyScopeCard
            title="No account selected"
            description="Choose an account to load live feedback volume analytics."
          />
        ) : preset === "custom" && (!customStartDate || !customEndDate) ? (
          <EmptyScopeCard
            title="Select a custom date range"
            description="Both start and end dates are required before live feedback volume can load."
          />
        ) : error ? (
          <Card className="border-destructive/30">
            <CardHeader>
              <CardTitle className="text-base">Unable to load feedback volume</CardTitle>
              <CardDescription>{error}</CardDescription>
            </CardHeader>
          </Card>
        ) : isLoading || !data ? (
          <LoadingDashboardState />
        ) : (
          <>
            <VolumeOverviewCard
              title={
                data.scope === "account"
                  ? "Account feedback volume"
                  : data.scope === "scorecard"
                    ? `${data.scorecard?.name || "Scorecard"} feedback volume`
                    : `${data.score?.name || "Score"} feedback volume`
              }
              description={`${currentWindowLabel} • ${timelineLabel} buckets • ${browserTimezone}`}
              points={data.points}
              summary={data.summary}
              bucketLabel={timelineLabel}
            />

            {data.scope === "account" ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold">Scorecards</h2>
                    <p className="text-sm text-muted-foreground">
                      Scorecards are sorted by collected feedback volume for the selected window.
                    </p>
                  </div>
                </div>
                <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                  {data.scorecardSeries.map((series) => (
                    <SeriesCard
                      key={series.key}
                      series={series}
                      onSelect={() => {
                        setSelectedScorecard(series.scorecardId || null);
                        setSelectedScore(null);
                      }}
                    />
                  ))}
                </div>
              </div>
            ) : null}

            {data.scope === "scorecard" ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold">Scores</h2>
                    <p className="text-sm text-muted-foreground">
                      Individual score timelines for {data.scorecard?.name || selectedScorecard}.
                    </p>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Showing {visibleScoreSeries.visibleCount} of {visibleScoreSeries.totalCount} scores
                  </div>
                </div>
                <div className="grid gap-4">
                  {visibleScoreSeries.visibleRows.map((series) => (
                    <SeriesCard
                      key={series.key}
                      series={series}
                      onSelect={() => setSelectedScore(series.scoreId || null)}
                      reportActions={
                        series.scoreId ? (
                          <FeedbackReportActionsMenu
                            scorecardId={selectedScorecard!}
                            scoreId={series.scoreId}
                            days={preset === "custom" ? undefined : Number(preset)}
                            startDate={preset === "custom" ? customStartDate : undefined}
                            endDate={preset === "custom" ? customEndDate : undefined}
                            timezone={browserTimezone}
                            weekStart="monday"
                            buttonLabel="Reports"
                          />
                        ) : null
                      }
                    />
                  ))}
                </div>
                {visibleScoreSeries.hasMore ? (
                  <div ref={visibleScoreSeries.sentinelRef} className="flex justify-center py-4">
                    <Button variant="ghost" size="sm" onClick={visibleScoreSeries.loadMore}>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading more scores
                    </Button>
                  </div>
                ) : null}
              </div>
            ) : null}

            {data.scope === "score" ? (
              <Card className="border-border/60">
                <CardHeader>
                  <CardTitle className="text-base">Deeper analysis</CardTitle>
                  <CardDescription>
                    Use the report menu to generate score-specific analysis such as contradictions or overview reports.
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-2">
                  <FeedbackReportActionsMenu
                    scorecardId={selectedScorecard!}
                    scoreId={selectedScore}
                    days={preset === "custom" ? undefined : Number(preset)}
                    startDate={preset === "custom" ? customStartDate : undefined}
                    endDate={preset === "custom" ? customEndDate : undefined}
                    timezone={browserTimezone}
                    weekStart="monday"
                    buttonLabel="Run score report"
                  />
                </CardContent>
              </Card>
            ) : null}

            {data.summary.feedback_items_total === 0 ? (
              <EmptyScopeCard
                title="No feedback collected in this window"
                description="The current scorecard / score scope has no feedback items for the selected range."
              />
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
