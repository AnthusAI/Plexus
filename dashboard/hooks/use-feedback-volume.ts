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

const ACCOUNT_FEEDBACK_ITEMS_QUERY = `
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

const SCORE_FEEDBACK_ITEMS_QUERY = `
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

interface UseFeedbackVolumeState {
  isLoading: boolean;
  error: string | null;
  data: FeedbackVolumeDashboardData | null;
}

async function fetchScorecardsForAccount(accountId: string): Promise<FeedbackVolumeNamedEntity[]> {
  const client = getClient();
  let nextToken: string | undefined;
  const scorecards: FeedbackVolumeNamedEntity[] = [];

  do {
    const result = await listFromModel<Schema["Scorecard"]["type"]>(
      client.models.Scorecard,
      { accountId: { eq: accountId } },
      nextToken,
      1000
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

  do {
    const result = await listFromModel<Schema["Score"]["type"]>(
      client.models.Score,
      { scorecardId: { eq: scorecardId } },
      nextToken,
      1000
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

async function paginatedFeedbackQuery(
  query: string,
  variables: Record<string, unknown>,
  dataKey: string
): Promise<FeedbackVolumeSourceItem[]> {
  const items: FeedbackVolumeSourceItem[] = [];
  let nextToken: string | null = null;
  const seenTokens = new Set<string>();

  do {
    if (nextToken) {
      if (seenTokens.has(nextToken)) {
        break;
      }
      seenTokens.add(nextToken);
    }

    const response: {
      data?: Record<string, FeedbackItemQueryResponse>;
      errors?: Array<{ message: string }>;
    } = await graphqlRequest<Record<string, FeedbackItemQueryResponse>>(query, {
      ...variables,
      nextToken,
      sortDirection: "DESC",
      limit: 1000,
    });

    if (response.errors?.length) {
      throw new Error(response.errors.map((error: { message: string }) => error.message).join(", "));
    }

    const result: FeedbackItemQueryResponse | undefined = response.data?.[dataKey];
    if (!result) {
      break;
    }

    items.push(...(result.items || []));
    nextToken = result.nextToken ?? null;
  } while (nextToken);

  return items;
}

function getFeedbackItemTimestamp(item: FeedbackVolumeSourceItem): number {
  const timestamp = item.editedAt || item.updatedAt || item.createdAt;
  if (!timestamp) {
    return 0;
  }
  const parsed = Date.parse(timestamp);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function mergeAndDedupeFeedbackItems(items: FeedbackVolumeSourceItem[]): FeedbackVolumeSourceItem[] {
  const byId = new Map<string, FeedbackVolumeSourceItem>();
  for (const item of items) {
    const existing = byId.get(item.id);
    if (!existing || getFeedbackItemTimestamp(item) >= getFeedbackItemTimestamp(existing)) {
      byId.set(item.id, item);
    }
  }
  return Array.from(byId.values());
}

async function fetchFeedbackItemsByAccountAndEditedAt(
  accountId: string,
  startDate: Date,
  endDate: Date
): Promise<FeedbackVolumeSourceItem[]> {
  return paginatedFeedbackQuery(ACCOUNT_FEEDBACK_ITEMS_QUERY, {
    accountId,
    editedAt: {
      between: [startDate.toISOString(), endDate.toISOString()],
    },
  }, "listFeedbackItemByAccountIdAndEditedAt");
}

async function fetchFeedbackItemsByAccountAndUpdatedAt(
  accountId: string,
  startDate: Date,
  endDate: Date
): Promise<FeedbackVolumeSourceItem[]> {
  return paginatedFeedbackQuery(ACCOUNT_FEEDBACK_ITEMS_UPDATED_AT_QUERY, {
    accountId,
    updatedAt: {
      between: [startDate.toISOString(), endDate.toISOString()],
    },
  }, "listFeedbackItemByAccountIdAndUpdatedAt");
}

async function fetchFeedbackItemsByScore(
  accountId: string,
  scorecardId: string,
  scoreId: string,
  startDate: Date,
  endDate: Date
): Promise<FeedbackVolumeSourceItem[]> {
  return paginatedFeedbackQuery(SCORE_FEEDBACK_ITEMS_QUERY, {
    accountId,
    compositeCondition: {
      between: [
        {
          scorecardId,
          scoreId,
          editedAt: startDate.toISOString(),
        },
        {
          scorecardId,
          scoreId,
          editedAt: endDate.toISOString(),
        },
      ],
    },
  }, "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndEditedAt");
}

async function fetchFeedbackItemsByScoreAndUpdatedAt(
  accountId: string,
  scorecardId: string,
  scoreId: string,
  startDate: Date,
  endDate: Date
): Promise<FeedbackVolumeSourceItem[]> {
  return paginatedFeedbackQuery(SCORE_FEEDBACK_ITEMS_UPDATED_AT_QUERY, {
    accountId,
    compositeCondition: {
      between: [
        {
          scorecardId,
          scoreId,
          updatedAt: startDate.toISOString(),
        },
        {
          scorecardId,
          scoreId,
          updatedAt: endDate.toISOString(),
        },
      ],
    },
  }, "listFeedbackItemByAccountIdAndScorecardIdAndScoreIdAndUpdatedAt");
}

async function fetchFeedbackItemsByAccountWindow(
  accountId: string,
  startDate: Date,
  endDate: Date
): Promise<FeedbackVolumeSourceItem[]> {
  const [byEditedAt, byUpdatedAt] = await Promise.all([
    fetchFeedbackItemsByAccountAndEditedAt(accountId, startDate, endDate),
    fetchFeedbackItemsByAccountAndUpdatedAt(accountId, startDate, endDate),
  ]);
  return mergeAndDedupeFeedbackItems([...byEditedAt, ...byUpdatedAt]);
}

async function fetchFeedbackItemsByScoreWindow(
  accountId: string,
  scorecardId: string,
  scoreId: string,
  startDate: Date,
  endDate: Date
): Promise<FeedbackVolumeSourceItem[]> {
  const [byEditedAt, byUpdatedAt] = await Promise.all([
    fetchFeedbackItemsByScore(accountId, scorecardId, scoreId, startDate, endDate),
    fetchFeedbackItemsByScoreAndUpdatedAt(accountId, scorecardId, scoreId, startDate, endDate),
  ]);
  return mergeAndDedupeFeedbackItems([...byEditedAt, ...byUpdatedAt]);
}

async function mapWithConcurrency<T, R>(
  values: T[],
  concurrency: number,
  mapper: (value: T, index: number) => Promise<R>
): Promise<R[]> {
  if (values.length === 0) {
    return [];
  }

  const resolvedConcurrency = Math.max(1, Math.min(concurrency, values.length));
  const results = new Array<R>(values.length);
  let nextIndex = 0;

  async function worker() {
    while (nextIndex < values.length) {
      const currentIndex = nextIndex;
      nextIndex += 1;
      results[currentIndex] = await mapper(values[currentIndex], currentIndex);
    }
  }

  await Promise.all(Array.from({ length: resolvedConcurrency }, () => worker()));
  return results;
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

  if (scope === "account") {
    const [scorecards, items] = await Promise.all([
      fetchScorecardsForAccount(accountId),
      fetchFeedbackItemsByAccountWindow(accountId, window.start, window.end),
    ]);

    return buildFeedbackVolumeDashboardData({
      scope,
      items,
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

  const [scorecards, scores] = await Promise.all([
    fetchScorecardsForAccount(accountId),
    fetchScoresForScorecard(scorecardId),
  ]);

  if (scope === "score") {
    if (!scoreId) {
      throw new Error("scoreId is required for score scope.");
    }

    const items = await fetchFeedbackItemsByScoreWindow(accountId, scorecardId, scoreId, window.start, window.end);
    return buildFeedbackVolumeDashboardData({
      scope,
      items,
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

  const perScoreItems = await mapWithConcurrency(scores, 4, async (score) =>
    fetchFeedbackItemsByScoreWindow(accountId, scorecardId, score.id, window.start, window.end)
  );
  const items = perScoreItems.flat();

  return buildFeedbackVolumeDashboardData({
    scope,
    items,
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
      });
      return;
    }

    if ((config.startDate && !config.endDate) || (!config.startDate && config.endDate)) {
      setState({
        isLoading: false,
        error: "Both start and end dates are required for a custom range.",
        data: null,
      });
      return;
    }

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setState((current) => ({
      ...current,
      isLoading: true,
      error: null,
    }));

    loadFeedbackVolumeDashboardData({
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
        });
      });
  }, [config.accountId, dependencyKey]);

  return state;
}
