"use client";

import React, { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import {
  CalendarDays,
  ChevronRight,
  FilePlus2,
  Loader2,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { useAccount } from "@/app/contexts/AccountContext";
import ScorecardContext from "@/components/ScorecardContext";
import { useFeedbackVolume } from "@/hooks/use-feedback-volume";
import { useIncrementalRows } from "@/components/blocks/useIncrementalRows";
import { ChartContainer } from "@/components/ui/chart";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
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
    <div className="rounded-md bg-popover p-3 text-xs text-popover-foreground">
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
  tone = "neutral",
}: {
  label: string;
  value: number;
  detail?: string;
  tone?: "neutral" | "changed" | "unchanged" | "invalid";
}) {
  const toneClass = {
    neutral: "bg-info",
    changed: "bg-false",
    unchanged: "bg-true",
    invalid: "bg-neutral",
  }[tone];

  return (
    <div className="rounded-lg bg-frame px-4 py-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className={cn("h-2 w-2 rounded-full", toneClass)} />
        <span>{label}</span>
      </div>
      <div className="mt-2">
        <div className="text-2xl font-semibold">{formatNumber(value)}</div>
        {detail ? <div className="mt-1 text-xs text-muted-foreground">{detail}</div> : null}
      </div>
    </div>
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
      <div className="rounded-lg bg-card px-4 py-3 text-sm text-muted-foreground">
        Loading feedback volume data...
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-lg bg-card p-4">
            <div className="pb-2">
              <div className="h-4 w-24 animate-pulse rounded bg-muted" />
            </div>
            <div className="space-y-2">
              <div className="h-8 w-20 animate-pulse rounded bg-muted" />
              <div className="h-3 w-32 animate-pulse rounded bg-muted" />
            </div>
          </div>
        ))}
      </div>
      <div className="rounded-lg bg-card p-4">
        <div className="space-y-2">
          <div className="h-5 w-40 animate-pulse rounded bg-muted" />
          <div className="h-4 w-56 animate-pulse rounded bg-muted" />
        </div>
        <div className="mt-4">
          <div className="h-[280px] animate-pulse rounded-lg bg-muted" />
        </div>
      </div>
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
    <div className="rounded-lg bg-card px-4 py-5">
      <div className="text-base font-semibold">{title}</div>
      <div className="mt-1 text-sm text-muted-foreground">{description}</div>
    </div>
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
            variant="ghost"
            size="sm"
            onClick={() => setPreset(option.value)}
            className={cn(
              "rounded-full px-3 shadow-none",
              preset === option.value
                ? "bg-secondary text-secondary-foreground hover:bg-secondary-selected"
                : "bg-card text-muted-foreground hover:bg-card-selected hover:text-foreground"
            )}
          >
            {option.label}
          </Button>
        ))}
      </div>
      {preset === "custom" ? (
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 rounded-lg bg-card px-3 py-2">
            <CalendarDays className="h-4 w-4 text-muted-foreground" />
            <Input
              type="date"
              value={customStartDate}
              onChange={(event) => setCustomStartDate(event.target.value)}
              className="h-8 w-[150px] border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
            />
          </div>
          <span className="text-sm text-muted-foreground">to</span>
          <div className="flex items-center gap-2 rounded-lg bg-card px-3 py-2">
            <CalendarDays className="h-4 w-4 text-muted-foreground" />
            <Input
              type="date"
              value={customEndDate}
              onChange={(event) => setCustomEndDate(event.target.value)}
              className="h-8 w-[150px] border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
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
    <div className="rounded-lg bg-card p-4">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="mt-4 space-y-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Total Feedback Items"
            value={summary.feedback_items_total}
            detail={`Buckets: ${bucketLabel}`}
            tone="neutral"
          />
          <MetricCard label="Changed" value={summary.feedback_items_changed} tone="changed" />
          <MetricCard label="Unchanged" value={summary.feedback_items_unchanged} tone="unchanged" />
          <MetricCard
            label="Invalid / Unclassified"
            value={summary.feedback_items_invalid_or_unclassified}
            detail={`Valid feedback: ${formatNumber(summary.feedback_items_valid)}`}
            tone="invalid"
          />
        </div>
        <div className="rounded-lg bg-background p-3">
          <FeedbackVolumeChart points={points} />
        </div>
      </div>
    </div>
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
    <div className="rounded-lg bg-card p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-1">
          <h3 className="text-base font-semibold">{series.label}</h3>
          <p className="text-sm text-muted-foreground">
            {hasFeedback
              ? `${formatNumber(series.summary.feedback_items_total)} feedback items in the selected window`
              : "No feedback in the selected window"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {reportActions}
          {onSelect ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={onSelect}
              className="bg-card-selected text-foreground shadow-none hover:bg-card-selected/80"
            >
              Open
              <ChevronRight className="h-4 w-4" />
            </Button>
          ) : null}
        </div>
      </div>
      <div className="mt-4 space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Total" value={series.summary.feedback_items_total} tone="neutral" />
          <MetricCard label="Changed" value={series.summary.feedback_items_changed} tone="changed" />
          <MetricCard label="Unchanged" value={series.summary.feedback_items_unchanged} tone="unchanged" />
          <MetricCard
            label="Invalid / Unclassified"
            value={series.summary.feedback_items_invalid_or_unclassified}
            tone="invalid"
          />
        </div>
        {hasFeedback ? (
          <div className="rounded-lg bg-background p-3">
            <FeedbackVolumeChart points={series.points} compact />
          </div>
        ) : (
          <div className="rounded-lg bg-frame px-3 py-4 text-sm text-muted-foreground">
            This scope has no collected feedback for the selected date window.
          </div>
        )}
      </div>
    </div>
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
        <Button
          variant="ghost"
          size="sm"
          disabled={isDispatching}
          className="bg-card text-foreground shadow-none hover:bg-card-selected"
        >
          {isDispatching ? <Loader2 className="h-4 w-4 animate-spin" /> : <FilePlus2 className="h-4 w-4" />}
          {buttonLabel}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64 border-0 bg-popover shadow-none">
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
  const showDiagnostics = process.env.NODE_ENV !== "production";

  return (
    <div className="h-full overflow-auto">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 p-4">
        {showDiagnostics ? (
          <div className="rounded-lg bg-card px-4 py-2 text-xs text-muted-foreground">
            {`debug: account=${selectedAccount?.id || "none"} loading=${String(isLoading)} error=${error || "none"} dataScope=${data?.scope || "none"} total=${data?.summary.feedback_items_total ?? 0} scorecards=${data?.scorecardSeries.length ?? 0} scores=${data?.scoreSeries.length ?? 0}`}
          </div>
        ) : null}
        <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
          <div className="flex flex-1 flex-col gap-3">
            <ScorecardContext
              selectedScorecard={selectedScorecard}
              setSelectedScorecard={setSelectedScorecard}
              selectedScore={selectedScore}
              setSelectedScore={setSelectedScore}
            />
            {selectedScore ? (
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span className="rounded-md bg-card px-3 py-1.5">
                  {data?.scorecard?.name || selectedScorecard} / {data?.score?.name || selectedScore}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedScore(null)}
                  className="bg-card text-muted-foreground shadow-none hover:bg-card-selected hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                  Clear score
                </Button>
              </div>
            ) : null}
          </div>
          <div className="flex flex-col gap-3 xl:items-end">
            <FeedbackWindowControls
              preset={preset}
              setPreset={setPreset}
              customStartDate={customStartDate}
              setCustomStartDate={setCustomStartDate}
              customEndDate={customEndDate}
              setCustomEndDate={setCustomEndDate}
            />
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
        </div>

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
          <div className="rounded-lg bg-card px-4 py-5">
            <div className="text-base font-semibold text-destructive">Unable to load feedback volume</div>
            <div className="mt-1 text-sm text-muted-foreground">{error}</div>
          </div>
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
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={visibleScoreSeries.loadMore}
                      className="bg-card text-muted-foreground shadow-none hover:bg-card-selected hover:text-foreground"
                    >
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading more scores
                    </Button>
                  </div>
                ) : null}
              </div>
            ) : null}

            {data.scope === "score" ? (
              <div className="rounded-lg bg-card p-4">
                <div className="space-y-1">
                  <div className="text-base font-semibold">Deeper analysis</div>
                  <div className="text-sm text-muted-foreground">
                    Use the report menu to generate score-specific analysis such as contradictions or overview reports.
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
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
                </div>
              </div>
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
