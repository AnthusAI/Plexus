"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { Schema } from "@/amplify/data/resource";
import { graphqlRequest } from "@/utils/amplify-client";
import { listFromModel } from "@/utils/amplify-helpers";
import { getClient } from "@/utils/data-operations";
import {
  buildFeedbackVolumeDashboardDataFromMetrics,
  pickAutoFeedbackVolumeBucketType,
  resolveFeedbackVolumeWindow,
  type FeedbackVolumeBucketType,
  type FeedbackVolumeDashboardData,
  type FeedbackVolumeMetricRecord,
  type FeedbackVolumeNamedEntity,
  type FeedbackVolumeScope,
  type FeedbackWeekStart,
} from "@/utils/feedback-volume";

type AggregatedMetricsRecord = Schema["AggregatedMetrics"]["type"];

const AGGREGATED_METRIC_FIELDS = `
  accountId
  compositeKey
  scorecardId
  scoreId
  recordType
  timeRangeStart
  timeRangeEnd
  numberOfMinutes
  count
  metadata
  complete
  createdAt
  updatedAt
`;

const ACCOUNT_FEEDBACK_VOLUME_QUERY = `
  query ListAggregatedMetricsByAccountRecordType(
    $accountId: String!
    $recordType: String!
    $startTime: String!
    $endTime: String!
    $nextToken: String
  ) {
    listAggregatedMetricsByAccountIdAndRecordTypeAndTimeRangeStart(
      accountId: $accountId
      recordTypeTimeRangeStart: {
        between: [
          { recordType: $recordType, timeRangeStart: $startTime }
          { recordType: $recordType, timeRangeStart: $endTime }
        ]
      }
      limit: 1000
      nextToken: $nextToken
    ) {
      items {
        ${AGGREGATED_METRIC_FIELDS}
      }
      nextToken
    }
  }
`;

const SCORECARD_FEEDBACK_VOLUME_QUERY = `
  query ListAggregatedMetricsByScorecardTimeRange(
    $scorecardId: String!
    $startTime: String!
    $endTime: String!
    $nextToken: String
  ) {
    listAggregatedMetricsByScorecardIdAndTimeRangeStartAndRecordType(
      scorecardId: $scorecardId
      timeRangeStartRecordType: {
        between: [
          { timeRangeStart: $startTime, recordType: "" }
          { timeRangeStart: $endTime, recordType: "\\uffff" }
        ]
      }
      limit: 1000
      nextToken: $nextToken
    ) {
      items {
        ${AGGREGATED_METRIC_FIELDS}
      }
      nextToken
    }
  }
`;

const SCORE_FEEDBACK_VOLUME_QUERY = `
  query ListAggregatedMetricsByScoreTimeRange(
    $scoreId: String!
    $startTime: String!
    $endTime: String!
    $nextToken: String
  ) {
    listAggregatedMetricsByScoreIdAndTimeRangeStartAndRecordType(
      scoreId: $scoreId
      timeRangeStartRecordType: {
        between: [
          { timeRangeStart: $startTime, recordType: "" }
          { timeRangeStart: $endTime, recordType: "\\uffff" }
        ]
      }
      limit: 1000
      nextToken: $nextToken
    ) {
      items {
        ${AGGREGATED_METRIC_FIELDS}
      }
      nextToken
    }
  }
`;

interface AggregatedMetricsQueryResponse {
  items: AggregatedMetricsRecord[];
  nextToken: string | null;
}

interface UseFeedbackVolumeConfig {
  accountId?: string | null;
  scorecardId?: string | null;
  scoreId?: string | null;
  days?: number;
  startDate?: Date;
  endDate?: Date;
  timezone: string;
  weekStart?: FeedbackWeekStart;
  bucketType?: FeedbackVolumeBucketType;
}

export interface FeedbackVolumeProgress {
  phase: "idle";
  pagesFetched: number;
  rawCount: number;
  uniqueCount: number;
}

interface UseFeedbackVolumeState {
  isLoading: boolean;
  error: string | null;
  data: FeedbackVolumeDashboardData | null;
  isPartial: boolean;
  progress: FeedbackVolumeProgress | null;
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timeoutId = setTimeout(() => reject(new Error(`${label} timed out after ${timeoutMs}ms`)), timeoutMs);
    promise.then(
      (value) => {
        clearTimeout(timeoutId);
        resolve(value);
      },
      (error) => {
        clearTimeout(timeoutId);
        reject(error);
      }
    );
  });
}

async function fetchScorecards(): Promise<FeedbackVolumeNamedEntity[]> {
  const client = getClient();
  let nextToken: string | undefined;
  const scorecards: FeedbackVolumeNamedEntity[] = [];
  const seenTokens = new Set<string>();

  do {
    if (nextToken) {
      if (seenTokens.has(nextToken)) break;
      seenTokens.add(nextToken);
    }

    const result = await withTimeout(
      listFromModel<Schema["Scorecard"]["type"]>(client.models.Scorecard, undefined, nextToken, 1000),
      8_000,
      "Scorecard list"
    );
    scorecards.push(
      ...result.data.map((scorecard) => ({
        id: scorecard.id,
        name: scorecard.name,
      }))
    );
    nextToken = result.nextToken ?? undefined;
  } while (nextToken);

  return scorecards.sort((left, right) => left.name.localeCompare(right.name));
}

async function fetchScoresForScorecard(scorecardId: string): Promise<FeedbackVolumeNamedEntity[]> {
  const client = getClient();
  let nextToken: string | undefined;
  const scores: FeedbackVolumeNamedEntity[] = [];
  const seenTokens = new Set<string>();

  do {
    if (nextToken) {
      if (seenTokens.has(nextToken)) break;
      seenTokens.add(nextToken);
    }

    const result = await withTimeout(
      listFromModel<Schema["Score"]["type"]>(
        client.models.Score,
        { scorecardId: { eq: scorecardId } },
        nextToken,
        1000
      ),
      8_000,
      `Score list for ${scorecardId}`
    );
    scores.push(
      ...result.data.map((score) => ({
        id: score.id,
        name: score.name,
      }))
    );
    nextToken = result.nextToken ?? undefined;
  } while (nextToken);

  return scores.sort((left, right) => left.name.localeCompare(right.name));
}

function normalizeMetricRecord(record: AggregatedMetricsRecord): FeedbackVolumeMetricRecord | null {
  if (!record.recordType || !record.timeRangeStart || !record.timeRangeEnd) {
    return null;
  }
  if (typeof record.numberOfMinutes !== "number" || typeof record.count !== "number") {
    return null;
  }

  return {
    accountId: record.accountId,
    compositeKey: record.compositeKey,
    recordType: record.recordType,
    scorecardId: record.scorecardId,
    scoreId: record.scoreId,
    timeRangeStart: record.timeRangeStart,
    timeRangeEnd: record.timeRangeEnd,
    numberOfMinutes: record.numberOfMinutes,
    count: record.count,
    metadata:
      record.metadata && typeof record.metadata === "object"
        ? {
            changedCount:
              typeof (record.metadata as Record<string, unknown>).changedCount === "number"
                ? ((record.metadata as Record<string, unknown>).changedCount as number)
                : 0,
            unchangedCount:
              typeof (record.metadata as Record<string, unknown>).unchangedCount === "number"
                ? ((record.metadata as Record<string, unknown>).unchangedCount as number)
                : 0,
            invalidCount:
              typeof (record.metadata as Record<string, unknown>).invalidCount === "number"
                ? ((record.metadata as Record<string, unknown>).invalidCount as number)
                : 0,
          }
        : undefined,
    complete: record.complete,
  };
}

function recordOverlapsWindow(record: FeedbackVolumeMetricRecord, start: Date, end: Date): boolean {
  const recordStart = new Date(record.timeRangeStart);
  const recordEnd = new Date(record.timeRangeEnd);
  if (Number.isNaN(recordStart.getTime()) || Number.isNaN(recordEnd.getTime())) {
    return false;
  }
  return recordStart < end && recordEnd > start;
}

async function paginatedAggregatedMetricsQuery(
  query: string,
  variables: Record<string, unknown>,
  dataKey: string
): Promise<FeedbackVolumeMetricRecord[]> {
  let nextToken: string | null = null;
  const seenTokens = new Set<string>();
  const records: FeedbackVolumeMetricRecord[] = [];

  do {
    if (nextToken) {
      if (seenTokens.has(nextToken)) break;
      seenTokens.add(nextToken);
    }

    const response: {
      data?: Record<string, AggregatedMetricsQueryResponse>;
      errors?: { message: string }[];
    } = await withTimeout(
      graphqlRequest<Record<string, AggregatedMetricsQueryResponse>>(query, {
        ...variables,
        nextToken,
      }),
      20_000,
      "Feedback aggregate query"
    );

    if (response.errors?.length) {
      throw new Error(response.errors.map((error) => error.message).join(", "));
    }

    const result = response.data?.[dataKey];
    if (!result) {
      break;
    }

    records.push(
      ...result.items
        .map((item) => normalizeMetricRecord(item))
        .filter((item): item is FeedbackVolumeMetricRecord => item !== null)
    );
    nextToken = result.nextToken ?? null;
  } while (nextToken);

  return records;
}

async function loadFeedbackVolumeDashboardData({
  accountId,
  scorecardId,
  scoreId,
  days,
  startDate,
  endDate,
  timezone,
  weekStart = "monday",
  bucketType,
}: {
  accountId: string;
  scorecardId?: string | null;
  scoreId?: string | null;
  days?: number;
  startDate?: Date;
  endDate?: Date;
  timezone: string;
  weekStart?: FeedbackWeekStart;
  bucketType?: FeedbackVolumeBucketType;
}): Promise<FeedbackVolumeDashboardData> {
  const scope: FeedbackVolumeScope = scoreId ? "score" : scorecardId ? "scorecard" : "account";
  const window = resolveFeedbackVolumeWindow({ days, startDate, endDate });
  const resolvedBucketType =
    bucketType ?? pickAutoFeedbackVolumeBucketType(window.start, window.end);
  const startIso = window.start.toISOString();
  const endIso = window.end.toISOString();

  if (scope === "account") {
    const [scorecards, summaryMetrics] = await Promise.all([
      fetchScorecards(),
      paginatedAggregatedMetricsQuery(
        ACCOUNT_FEEDBACK_VOLUME_QUERY,
        {
          accountId,
          recordType: "feedbackItemsByScorecard",
          startTime: startIso,
          endTime: endIso,
        },
        "listAggregatedMetricsByAccountIdAndRecordTypeAndTimeRangeStart"
      ),
    ]);

    const filteredSummaryMetrics = summaryMetrics.filter((record) =>
      record.recordType === "feedbackItemsByScorecard" && recordOverlapsWindow(record, window.start, window.end)
    );

    return buildFeedbackVolumeDashboardDataFromMetrics({
      scope,
      summaryMetrics: filteredSummaryMetrics,
      scorecardSeriesMetrics: filteredSummaryMetrics,
      scorecards,
      timeZone: timezone,
      weekStart,
      bucketType: resolvedBucketType,
      window,
    });
  }

  if (!scorecardId) {
    throw new Error("scorecardId is required for scorecard and score scoped feedback volume.");
  }

  if (scope === "score") {
    const [scorecards, scores, summaryMetrics] = await Promise.all([
      fetchScorecards(),
      fetchScoresForScorecard(scorecardId),
      paginatedAggregatedMetricsQuery(
        SCORE_FEEDBACK_VOLUME_QUERY,
        {
          scoreId,
          startTime: startIso,
          endTime: endIso,
        },
        "listAggregatedMetricsByScoreIdAndTimeRangeStartAndRecordType"
      ),
    ]);

    const filteredSummaryMetrics = summaryMetrics.filter((record) =>
      record.recordType === "feedbackItemsByScore"
      && record.scoreId === scoreId
      && recordOverlapsWindow(record, window.start, window.end)
    );

    return buildFeedbackVolumeDashboardDataFromMetrics({
      scope,
      summaryMetrics: filteredSummaryMetrics,
      scorecards,
      scores,
      selectedScorecardId: scorecardId,
      selectedScoreId: scoreId,
      timeZone: timezone,
      weekStart,
      bucketType: resolvedBucketType,
      window,
    });
  }

  const [scorecards, scores, allMetrics] = await Promise.all([
    fetchScorecards(),
    fetchScoresForScorecard(scorecardId),
    paginatedAggregatedMetricsQuery(
      SCORECARD_FEEDBACK_VOLUME_QUERY,
      {
        scorecardId,
        startTime: startIso,
        endTime: endIso,
      },
      "listAggregatedMetricsByScorecardIdAndTimeRangeStartAndRecordType"
    ),
  ]);

  const filteredMetrics = allMetrics.filter((record) =>
    record.scorecardId === scorecardId && recordOverlapsWindow(record, window.start, window.end)
  );

  return buildFeedbackVolumeDashboardDataFromMetrics({
    scope,
    summaryMetrics: filteredMetrics.filter((record) => record.recordType === "feedbackItemsByScorecard"),
    scoreSeriesMetrics: filteredMetrics.filter((record) => record.recordType === "feedbackItemsByScore"),
    scorecards,
    scores,
    selectedScorecardId: scorecardId,
    timeZone: timezone,
    weekStart,
    bucketType: resolvedBucketType,
    window,
  });
}

export function useFeedbackVolume(config: UseFeedbackVolumeConfig): UseFeedbackVolumeState {
  const [state, setState] = useState<UseFeedbackVolumeState>({
    isLoading: false,
    error: null,
    data: null,
    isPartial: false,
    progress: null,
  });
  const requestIdRef = useRef(0);

  const dependencyKey = useMemo(
    () =>
      JSON.stringify({
        accountId: config.accountId || null,
        scorecardId: config.scorecardId || null,
        scoreId: config.scoreId || null,
        days: config.days ?? null,
        startDate: config.startDate?.toISOString() || null,
        endDate: config.endDate?.toISOString() || null,
        timezone: config.timezone,
        weekStart: config.weekStart || "monday",
        bucketType: config.bucketType || null,
      }),
    [
      config.accountId,
      config.scorecardId,
      config.scoreId,
      config.days,
      config.startDate,
      config.endDate,
      config.timezone,
      config.weekStart,
      config.bucketType,
    ]
  );

  useEffect(() => {
    if (!config.accountId) {
      setState({
        isLoading: false,
        error: null,
        data: null,
        isPartial: false,
        progress: null,
      });
      return;
    }

    if ((config.startDate && !config.endDate) || (!config.startDate && config.endDate)) {
      setState({
        isLoading: false,
        error: "Both start and end dates are required for a custom range.",
        data: null,
        isPartial: false,
        progress: null,
      });
      return;
    }

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setState({
      isLoading: true,
      error: null,
      data: null,
      isPartial: false,
      progress: null,
    });

    void loadFeedbackVolumeDashboardData({
      accountId: config.accountId,
      scorecardId: config.scorecardId || undefined,
      scoreId: config.scoreId || undefined,
      days: config.days,
      startDate: config.startDate,
      endDate: config.endDate,
      timezone: config.timezone,
      weekStart: config.weekStart,
      bucketType: config.bucketType,
    })
      .then((data) => {
        if (requestIdRef.current !== requestId) {
          return;
        }
        setState({
          isLoading: false,
          error: null,
          data,
          isPartial: false,
          progress: null,
        });
      })
      .catch((error) => {
        if (requestIdRef.current !== requestId) {
          return;
        }
        setState({
          isLoading: false,
          error: error instanceof Error ? error.message : "Failed to load feedback volume.",
          data: null,
          isPartial: false,
          progress: null,
        });
      });
  }, [config.accountId, dependencyKey]);

  return state;
}
