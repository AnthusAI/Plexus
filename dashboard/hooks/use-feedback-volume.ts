"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { Schema } from "@/amplify/data/resource";
import { graphqlRequest } from "@/utils/amplify-client";
import { listFromModel } from "@/utils/amplify-helpers";
import { getClient } from "@/utils/data-operations";
import {
  buildFeedbackVolumeDashboardData,
  pickAutoFeedbackVolumeBucketType,
  resolveFeedbackVolumeWindow,
  type FeedbackVolumeBucketType,
  type FeedbackVolumeDashboardData,
  type FeedbackVolumeNamedEntity,
  type FeedbackVolumeScope,
  type FeedbackVolumeSourceItem,
  type FeedbackWeekStart,
} from "@/utils/feedback-volume";

const ACCOUNT_FEEDBACK_ITEMS_EDITED_AT_QUERY = `
  query ListFeedbackItemByAccountIdAndEditedAt(
    $accountId: String!
    $editedAt: ModelStringKeyConditionInput
    $limit: Int
    $nextToken: String
    $sortDirection: ModelSortDirection
  ) {
    listFeedbackItemByAccountIdAndEditedAt(
      accountId: $accountId
      editedAt: $editedAt
      limit: $limit
      nextToken: $nextToken
      sortDirection: $sortDirection
    ) {
      items {
        id
        scorecardId
        scoreId
        itemId
        initialAnswerValue
        finalAnswerValue
        isInvalid
        editedAt
        updatedAt
        createdAt
      }
      nextToken
    }
  }
`;

const ACCOUNT_FEEDBACK_ITEMS_UPDATED_AT_QUERY = `
  query ListFeedbackItemByAccountIdAndUpdatedAt(
    $accountId: String!
    $updatedAt: ModelStringKeyConditionInput
    $limit: Int
    $nextToken: String
    $sortDirection: ModelSortDirection
  ) {
    listFeedbackItemByAccountIdAndUpdatedAt(
      accountId: $accountId
      updatedAt: $updatedAt
      limit: $limit
      nextToken: $nextToken
      sortDirection: $sortDirection
    ) {
      items {
        id
        scorecardId
        scoreId
        itemId
        initialAnswerValue
        finalAnswerValue
        isInvalid
        editedAt
        updatedAt
        createdAt
      }
      nextToken
    }
  }
`;

const SCORE_FEEDBACK_ITEMS_EDITED_AT_QUERY = `
  query ListFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
    $accountId: String!
    $compositeCondition: ModelFeedbackItemByAccountScorecardScoreEditedAtCompositeKeyConditionInput
    $limit: Int
    $nextToken: String
    $sortDirection: ModelSortDirection
  ) {
    listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt(
      accountId: $accountId
      scorecardIdScoreIdEditedAt: $compositeCondition
      limit: $limit
      nextToken: $nextToken
      sortDirection: $sortDirection
    ) {
      items {
        id
        scorecardId
        scoreId
        itemId
        initialAnswerValue
        finalAnswerValue
        isInvalid
        editedAt
        updatedAt
        createdAt
      }
      nextToken
    }
  }
`;

const SCORE_FEEDBACK_ITEMS_UPDATED_AT_QUERY = `
  query ListFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt(
    $accountId: String!
    $compositeCondition: ModelFeedbackItemByAccountScorecardScoreUpdatedAtCompositeKeyConditionInput
    $limit: Int
    $nextToken: String
    $sortDirection: ModelSortDirection
  ) {
    listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt(
      accountId: $accountId
      scorecardIdScoreIdUpdatedAt: $compositeCondition
      limit: $limit
      nextToken: $nextToken
      sortDirection: $sortDirection
    ) {
      items {
        id
        scorecardId
        scoreId
        itemId
        initialAnswerValue
        finalAnswerValue
        isInvalid
        editedAt
        updatedAt
        createdAt
      }
      nextToken
    }
  }
`;

interface FeedbackItemQueryResponse {
  items: FeedbackVolumeSourceItem[];
  nextToken: string | null;
}

interface PaginatedQueryOptions {
  limit?: number;
  timeoutMs?: number;
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
  phase: "fetching_edited" | "fetching_updated" | "finalizing";
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

interface SnapshotContext {
  scope: FeedbackVolumeScope;
  window: ReturnType<typeof resolveFeedbackVolumeWindow>;
  bucketType: FeedbackVolumeBucketType;
  timeZone: string;
  weekStart: FeedbackWeekStart;
  selectedScorecardId?: string | null;
  selectedScoreId?: string | null;
}

interface SnapshotOptions extends SnapshotContext {
  itemMap: Map<string, FeedbackVolumeSourceItem>;
  scorecards: FeedbackVolumeNamedEntity[];
  scores: FeedbackVolumeNamedEntity[];
}

interface ProgressiveLoadOptions extends SnapshotContext {
  accountId: string;
  onProgress?: (snapshot: {
    data: FeedbackVolumeDashboardData;
    progress: FeedbackVolumeProgress;
  }) => void;
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
  let pages = 0;

  do {
    if (nextToken) {
      if (seenTokens.has(nextToken)) break;
      seenTokens.add(nextToken);
    }
    if (pages >= 100) break;

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
    pages += 1;
  } while (nextToken);

  return scorecards.sort((left, right) => left.name.localeCompare(right.name));
}

async function fetchScoresForScorecard(scorecardId: string): Promise<FeedbackVolumeNamedEntity[]> {
  const client = getClient();
  let nextToken: string | undefined;
  const scores: FeedbackVolumeNamedEntity[] = [];
  const seenTokens = new Set<string>();
  let pages = 0;

  do {
    if (nextToken) {
      if (seenTokens.has(nextToken)) break;
      seenTokens.add(nextToken);
    }
    if (pages >= 100) break;

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
    pages += 1;
  } while (nextToken);

  return scores.sort((left, right) => left.name.localeCompare(right.name));
}

function getFeedbackItemTimestamp(item: FeedbackVolumeSourceItem): number {
  const timestamp = item.editedAt || item.updatedAt || item.createdAt;
  if (!timestamp) return 0;
  const parsed = Date.parse(timestamp);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function upsertFeedbackItems(itemMap: Map<string, FeedbackVolumeSourceItem>, items: FeedbackVolumeSourceItem[]): void {
  for (const item of items) {
    const existing = itemMap.get(item.id);
    if (!existing || getFeedbackItemTimestamp(item) >= getFeedbackItemTimestamp(existing)) {
      itemMap.set(item.id, item);
    }
  }
}

function createDashboardSnapshot({
  scope,
  itemMap,
  scorecards,
  scores,
  selectedScorecardId,
  selectedScoreId,
  timeZone,
  weekStart,
  bucketType,
  window,
}: SnapshotOptions): FeedbackVolumeDashboardData {
  return buildFeedbackVolumeDashboardData({
    scope,
    items: Array.from(itemMap.values()),
    scorecards,
    scores,
    selectedScorecardId,
    selectedScoreId,
    timeZone,
    weekStart,
    bucketType,
    window,
  });
}

async function paginatedFeedbackQuery(
  query: string,
  variables: Record<string, unknown>,
  dataKey: string,
  onPage: (items: FeedbackVolumeSourceItem[]) => void | Promise<void>,
  options: PaginatedQueryOptions = {}
): Promise<number> {
  const limit = options.limit ?? 1000;
  const timeoutMs = options.timeoutMs ?? 20_000;
  let nextToken: string | null = null;
  const seenTokens = new Set<string>();
  let pagesFetched = 0;

  do {
    if (nextToken) {
      if (seenTokens.has(nextToken)) {
        break;
      }
      seenTokens.add(nextToken);
    }

    const response: {
      data?: Record<string, FeedbackItemQueryResponse>;
      errors?: { message: string }[];
    } = await withTimeout(
      graphqlRequest<Record<string, FeedbackItemQueryResponse>>(query, {
        ...variables,
        nextToken,
        sortDirection: "DESC",
        limit,
      }),
      timeoutMs,
      "Feedback query"
    );

    if (response.errors?.length) {
      throw new Error(response.errors.map((error: { message: string }) => error.message).join(", "));
    }

    const result: FeedbackItemQueryResponse | undefined = response.data?.[dataKey];
    if (!result) {
      break;
    }

    pagesFetched += 1;
    await onPage(result.items || []);
    nextToken = result.nextToken ?? null;
  } while (nextToken);

  return pagesFetched;
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
  onProgress,
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
  onProgress?: ProgressiveLoadOptions["onProgress"];
}): Promise<FeedbackVolumeDashboardData> {
  const scope: FeedbackVolumeScope = scoreId ? "score" : scorecardId ? "scorecard" : "account";
  const window = resolveFeedbackVolumeWindow({ days, startDate, endDate });
  const resolvedBucketType =
    bucketType ?? pickAutoFeedbackVolumeBucketType(window.start, window.end);

  const context: SnapshotContext = {
    scope,
    window,
    bucketType: resolvedBucketType,
    timeZone: timezone,
    weekStart,
    selectedScorecardId: scorecardId || undefined,
    selectedScoreId: scoreId || undefined,
  };

  const itemMap = new Map<string, FeedbackVolumeSourceItem>();
  let scorecards: FeedbackVolumeNamedEntity[] = [];
  let scores: FeedbackVolumeNamedEntity[] = [];
  let currentPhase: FeedbackVolumeProgress["phase"] = "fetching_edited";
  let pagesFetched = 0;
  let rawCount = 0;

  const publish = () => {
    if (!onProgress) return;
    onProgress({
      data: createDashboardSnapshot({
        ...context,
        itemMap,
        scorecards,
        scores,
      }),
      progress: {
        phase: currentPhase,
        pagesFetched,
        rawCount,
        uniqueCount: itemMap.size,
      },
    });
  };

  const absorbPage = async (
    phase: FeedbackVolumeProgress["phase"],
    pageItems: FeedbackVolumeSourceItem[]
  ) => {
    currentPhase = phase;
    pagesFetched += 1;
    rawCount += pageItems.length;
    upsertFeedbackItems(itemMap, pageItems);
    publish();
  };

  const scorecardsPromise = fetchScorecards()
    .then((result) => {
      scorecards = result;
      if (itemMap.size > 0) publish();
      return result;
    })
    .catch(() => {
      scorecards = [];
      return [];
    });

  if (scope === "account") {
    await paginatedFeedbackQuery(
      ACCOUNT_FEEDBACK_ITEMS_EDITED_AT_QUERY,
      {
        accountId,
        editedAt: {
          between: [window.start.toISOString(), window.end.toISOString()],
        },
      },
      "listFeedbackItemByAccountIdAndEditedAt",
      (pageItems) => absorbPage("fetching_edited", pageItems)
    );

    await paginatedFeedbackQuery(
      ACCOUNT_FEEDBACK_ITEMS_UPDATED_AT_QUERY,
      {
        accountId,
        updatedAt: {
          between: [window.start.toISOString(), window.end.toISOString()],
        },
      },
      "listFeedbackItemByAccountIdAndUpdatedAt",
      (pageItems) => absorbPage("fetching_updated", pageItems)
    );

    scorecards = await scorecardsPromise;
    currentPhase = "finalizing";
    publish();

    return createDashboardSnapshot({
      ...context,
      itemMap,
      scorecards,
      scores,
    });
  }

  if (!scorecardId) {
    throw new Error("scorecardId is required for scorecard and score scoped feedback volume.");
  }

  const scoresPromise = fetchScoresForScorecard(scorecardId)
    .then((result) => {
      scores = result;
      if (itemMap.size > 0) publish();
      return result;
    })
    .catch(() => {
      scores = [];
      return [];
    });

  if (scope === "score") {
    await paginatedFeedbackQuery(
      SCORE_FEEDBACK_ITEMS_EDITED_AT_QUERY,
      {
        accountId,
        compositeCondition: {
          between: [
            {
              scorecardId,
              scoreId,
              editedAt: window.start.toISOString(),
            },
            {
              scorecardId,
              scoreId,
              editedAt: window.end.toISOString(),
            },
          ],
        },
      },
      "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt",
      (pageItems) => absorbPage("fetching_edited", pageItems)
    );

    await paginatedFeedbackQuery(
      SCORE_FEEDBACK_ITEMS_UPDATED_AT_QUERY,
      {
        accountId,
        compositeCondition: {
          between: [
            {
              scorecardId,
              scoreId,
              updatedAt: window.start.toISOString(),
            },
            {
              scorecardId,
              scoreId,
              updatedAt: window.end.toISOString(),
            },
          ],
        },
      },
      "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt",
      (pageItems) => absorbPage("fetching_updated", pageItems)
    );

    scorecards = await scorecardsPromise;
    scores = await scoresPromise;
    currentPhase = "finalizing";
    publish();

    return createDashboardSnapshot({
      ...context,
      itemMap,
      scorecards,
      scores,
    });
  }

  scores = await scoresPromise;

  for (const score of scores) {
    await paginatedFeedbackQuery(
      SCORE_FEEDBACK_ITEMS_EDITED_AT_QUERY,
      {
        accountId,
        compositeCondition: {
          between: [
            {
              scorecardId,
              scoreId: score.id,
              editedAt: window.start.toISOString(),
            },
            {
              scorecardId,
              scoreId: score.id,
              editedAt: window.end.toISOString(),
            },
          ],
        },
      },
      "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt",
      (pageItems) => absorbPage("fetching_edited", pageItems)
    );
  }

  for (const score of scores) {
    await paginatedFeedbackQuery(
      SCORE_FEEDBACK_ITEMS_UPDATED_AT_QUERY,
      {
        accountId,
        compositeCondition: {
          between: [
            {
              scorecardId,
              scoreId: score.id,
              updatedAt: window.start.toISOString(),
            },
            {
              scorecardId,
              scoreId: score.id,
              updatedAt: window.end.toISOString(),
            },
          ],
        },
      },
      "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt",
      (pageItems) => absorbPage("fetching_updated", pageItems)
    );
  }

  scorecards = await scorecardsPromise;
  currentPhase = "finalizing";
  publish();

  return createDashboardSnapshot({
    ...context,
    itemMap,
    scorecards,
    scores,
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
    setState((current) => ({
      ...current,
      isLoading: true,
      error: null,
      progress: null,
    }));

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
      onProgress: ({ data, progress }) => {
        if (requestIdRef.current !== requestId) {
          return;
        }
        setState({
          isLoading: true,
          error: null,
          data,
          isPartial: true,
          progress,
        });
      },
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
        setState((current) => ({
          ...current,
          isLoading: false,
          error: error instanceof Error ? error.message : "Failed to load feedback volume.",
        }));
      });
  }, [config.accountId, dependencyKey]);

  return state;
}
