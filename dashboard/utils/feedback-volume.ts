const DAY_MS = 24 * 60 * 60 * 1000;

export type FeedbackVolumeBucketType =
  | "trailing_1d"
  | "trailing_7d"
  | "trailing_14d"
  | "trailing_30d"
  | "calendar_day"
  | "calendar_week"
  | "calendar_biweek"
  | "calendar_month";

export type FeedbackVolumeScope = "account" | "scorecard" | "score";
export type FeedbackWeekStart = "monday" | "sunday";

export interface FeedbackVolumeSourceItem {
  id: string;
  scorecardId?: string | null;
  scoreId?: string | null;
  itemId?: string | null;
  initialAnswerValue?: string | null;
  finalAnswerValue?: string | null;
  editedAt?: string | null;
  updatedAt?: string | null;
  createdAt?: string | null;
  isInvalid?: boolean | number | string | null;
}

export interface FeedbackVolumePoint {
  bucket_index: number;
  label: string;
  start: string;
  end: string;
  feedback_items_total: number;
  feedback_items_valid: number;
  feedback_items_unchanged: number;
  feedback_items_changed: number;
  feedback_items_invalid_or_unclassified: number;
}

export interface FeedbackVolumeSummary {
  feedback_items_total: number;
  feedback_items_valid: number;
  feedback_items_unchanged: number;
  feedback_items_changed: number;
  feedback_items_invalid_or_unclassified: number;
}

export interface FeedbackVolumeSeries {
  key: string;
  scope: "scorecard" | "score";
  label: string;
  scorecardId?: string | null;
  scorecardName?: string | null;
  scoreId?: string | null;
  scoreName?: string | null;
  points: FeedbackVolumePoint[];
  summary: FeedbackVolumeSummary;
}

export interface FeedbackVolumeNamedEntity {
  id: string;
  name: string;
}

export interface FeedbackVolumeWindow {
  start: Date;
  end: Date;
  label: string;
  mode: "days" | "explicit";
  days?: number;
}

export interface FeedbackVolumeDateRange {
  start: string;
  end: string;
  label: string;
}

export interface FeedbackVolumeBucketPolicy {
  bucket_type: FeedbackVolumeBucketType;
  bucket_count: number;
  timezone: string;
  week_start: FeedbackWeekStart;
  window_mode: "exact_window";
}

export interface FeedbackVolumeDashboardData {
  scope: FeedbackVolumeScope;
  scorecard: FeedbackVolumeNamedEntity | null;
  score: FeedbackVolumeNamedEntity | null;
  summary: FeedbackVolumeSummary;
  points: FeedbackVolumePoint[];
  scorecardSeries: FeedbackVolumeSeries[];
  scoreSeries: FeedbackVolumeSeries[];
  dateRange: FeedbackVolumeDateRange;
  bucketPolicy: FeedbackVolumeBucketPolicy;
}

export interface BuildFeedbackVolumeDashboardDataInput {
  scope: FeedbackVolumeScope;
  items: FeedbackVolumeSourceItem[];
  scorecards?: FeedbackVolumeNamedEntity[];
  scores?: FeedbackVolumeNamedEntity[];
  selectedScorecardId?: string | null;
  selectedScoreId?: string | null;
  timeZone: string;
  weekStart?: FeedbackWeekStart;
  bucketType: FeedbackVolumeBucketType;
  window: FeedbackVolumeWindow;
}

interface TimeBucket {
  start: Date;
  end: Date;
  label: string;
}

interface ZonedDateParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
  millisecond: number;
}

const TRAILING_BUCKET_DAYS: Record<Extract<FeedbackVolumeBucketType, `trailing_${string}`>, number> = {
  trailing_1d: 1,
  trailing_7d: 7,
  trailing_14d: 14,
  trailing_30d: 30,
};

const formatterCache = new Map<string, Intl.DateTimeFormat>();

function getFormatter(timeZone: string): Intl.DateTimeFormat {
  const cacheKey = timeZone;
  const cached = formatterCache.get(cacheKey);
  if (cached) return cached;

  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  formatterCache.set(cacheKey, formatter);
  return formatter;
}

function parseZonedParts(date: Date, timeZone: string): ZonedDateParts {
  const parts = getFormatter(timeZone).formatToParts(date);
  const map = new Map(parts.map((part) => [part.type, part.value]));
  return {
    year: Number(map.get("year") || 0),
    month: Number(map.get("month") || 1),
    day: Number(map.get("day") || 1),
    hour: Number(map.get("hour") || 0),
    minute: Number(map.get("minute") || 0),
    second: Number(map.get("second") || 0),
    millisecond: date.getUTCMilliseconds(),
  };
}

function getTimeZoneOffsetMinutes(date: Date, timeZone: string): number {
  const parts = parseZonedParts(date, timeZone);
  const utcMillis = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
    parts.second,
    parts.millisecond
  );
  return (utcMillis - date.getTime()) / 60000;
}

function zonedPartsToDate(parts: ZonedDateParts, timeZone: string): Date {
  const utcGuess = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
    parts.second,
    parts.millisecond
  );
  let offset = getTimeZoneOffsetMinutes(new Date(utcGuess), timeZone);
  let resolved = new Date(utcGuess - offset * 60_000);
  const adjustedOffset = getTimeZoneOffsetMinutes(resolved, timeZone);
  if (adjustedOffset !== offset) {
    offset = adjustedOffset;
    resolved = new Date(utcGuess - offset * 60_000);
  }
  return resolved;
}

function formatDateOnly(parts: Pick<ZonedDateParts, "year" | "month" | "day">): string {
  return [
    parts.year.toString().padStart(4, "0"),
    parts.month.toString().padStart(2, "0"),
    parts.day.toString().padStart(2, "0"),
  ].join("-");
}

function formatMonthOnly(parts: Pick<ZonedDateParts, "year" | "month">): string {
  return [
    parts.year.toString().padStart(4, "0"),
    parts.month.toString().padStart(2, "0"),
  ].join("-");
}

function addDaysToParts(parts: ZonedDateParts, days: number): ZonedDateParts {
  const next = new Date(
    Date.UTC(parts.year, parts.month - 1, parts.day + days, parts.hour, parts.minute, parts.second, parts.millisecond)
  );
  return {
    year: next.getUTCFullYear(),
    month: next.getUTCMonth() + 1,
    day: next.getUTCDate(),
    hour: next.getUTCHours(),
    minute: next.getUTCMinutes(),
    second: next.getUTCSeconds(),
    millisecond: next.getUTCMilliseconds(),
  };
}

function addMonthsToParts(parts: ZonedDateParts, months: number): ZonedDateParts {
  const next = new Date(
    Date.UTC(parts.year, parts.month - 1 + months, 1, parts.hour, parts.minute, parts.second, parts.millisecond)
  );
  return {
    year: next.getUTCFullYear(),
    month: next.getUTCMonth() + 1,
    day: 1,
    hour: next.getUTCHours(),
    minute: next.getUTCMinutes(),
    second: next.getUTCSeconds(),
    millisecond: next.getUTCMilliseconds(),
  };
}

function addZonedDays(date: Date, days: number, timeZone: string): Date {
  return zonedPartsToDate(addDaysToParts(parseZonedParts(date, timeZone), days), timeZone);
}

function addZonedMonths(date: Date, months: number, timeZone: string): Date {
  return zonedPartsToDate(addMonthsToParts(parseZonedParts(date, timeZone), months), timeZone);
}

function startOfZonedDay(date: Date, timeZone: string): Date {
  const parts = parseZonedParts(date, timeZone);
  return zonedPartsToDate(
    {
      ...parts,
      hour: 0,
      minute: 0,
      second: 0,
      millisecond: 0,
    },
    timeZone
  );
}

function startOfZonedMonth(date: Date, timeZone: string): Date {
  const parts = parseZonedParts(date, timeZone);
  return zonedPartsToDate(
    {
      year: parts.year,
      month: parts.month,
      day: 1,
      hour: 0,
      minute: 0,
      second: 0,
      millisecond: 0,
    },
    timeZone
  );
}

function startOfZonedWeek(date: Date, timeZone: string, weekStart: FeedbackWeekStart): Date {
  const dayStart = startOfZonedDay(date, timeZone);
  const parts = parseZonedParts(dayStart, timeZone);
  const weekDay = new Date(Date.UTC(parts.year, parts.month - 1, parts.day)).getUTCDay();
  const weekStartIndex = weekStart === "monday" ? 1 : 0;
  const daysBack = (weekDay - weekStartIndex + 7) % 7;
  return addZonedDays(dayStart, -daysBack, timeZone);
}

function startOfZonedBiweek(date: Date, timeZone: string, weekStart: FeedbackWeekStart): Date {
  const weekStartDate = startOfZonedWeek(date, timeZone, weekStart);
  const epoch = zonedPartsToDate(
    {
      year: 1970,
      month: 1,
      day: weekStart === "monday" ? 5 : 4,
      hour: 0,
      minute: 0,
      second: 0,
      millisecond: 0,
    },
    timeZone
  );
  const weeksSinceEpoch = Math.floor((weekStartDate.getTime() - epoch.getTime()) / (7 * DAY_MS));
  return addZonedDays(epoch, Math.floor(weeksSinceEpoch / 2) * 14, timeZone);
}

function labelForBucket(bucketStart: Date, bucketType: FeedbackVolumeBucketType, timeZone: string): string {
  const parts = parseZonedParts(bucketStart, timeZone);
  if (bucketType === "calendar_month") {
    return formatMonthOnly(parts);
  }
  return formatDateOnly(parts);
}

function advanceCalendarPeriod(
  periodStart: Date,
  bucketType: FeedbackVolumeBucketType,
  timeZone: string
): Date {
  switch (bucketType) {
    case "calendar_day":
      return addZonedDays(periodStart, 1, timeZone);
    case "calendar_week":
      return addZonedDays(periodStart, 7, timeZone);
    case "calendar_biweek":
      return addZonedDays(periodStart, 14, timeZone);
    case "calendar_month":
      return addZonedMonths(periodStart, 1, timeZone);
    default:
      throw new Error(`Unsupported calendar bucket type: ${bucketType}`);
  }
}

function getCalendarPeriodStart(
  value: Date,
  bucketType: FeedbackVolumeBucketType,
  timeZone: string,
  weekStart: FeedbackWeekStart
): Date {
  switch (bucketType) {
    case "calendar_day":
      return startOfZonedDay(value, timeZone);
    case "calendar_week":
      return startOfZonedWeek(value, timeZone, weekStart);
    case "calendar_biweek":
      return startOfZonedBiweek(value, timeZone, weekStart);
    case "calendar_month":
      return startOfZonedMonth(value, timeZone);
    default:
      throw new Error(`Unsupported calendar bucket type: ${bucketType}`);
  }
}

function getBucketStartIndex(timestamp: Date, buckets: TimeBucket[]): number {
  return buckets.findIndex((bucket) => timestamp >= bucket.start && timestamp < bucket.end);
}

export function pickAutoFeedbackVolumeBucketType(start: Date, end: Date): Extract<
  FeedbackVolumeBucketType,
  "calendar_day" | "calendar_week" | "calendar_month"
> {
  const durationDays = Math.max(1, Math.ceil((end.getTime() - start.getTime()) / DAY_MS));
  if (durationDays <= 14) {
    return "calendar_day";
  }
  if (durationDays <= 180) {
    return "calendar_week";
  }
  return "calendar_month";
}

export function parseBooleanLike(value: unknown, defaultValue = false): boolean {
  if (value === null || value === undefined) return defaultValue;
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  const normalized = String(value).trim().toLowerCase();
  if (["1", "true", "yes", "y", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "n", "off"].includes(normalized)) return false;
  return defaultValue;
}

export function getFeedbackVolumeTimestamp(item: FeedbackVolumeSourceItem): Date | null {
  const timestamp = item.editedAt || item.updatedAt || item.createdAt;
  if (!timestamp) return null;
  const parsed = new Date(timestamp);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function classifyFeedbackVolumeItem(
  item: FeedbackVolumeSourceItem
): "unchanged" | "changed" | "invalid_or_unclassified" {
  if (parseBooleanLike(item.isInvalid, false)) {
    return "invalid_or_unclassified";
  }
  if (item.initialAnswerValue == null || item.finalAnswerValue == null) {
    return "invalid_or_unclassified";
  }
  if (String(item.initialAnswerValue) !== String(item.finalAnswerValue)) {
    return "changed";
  }
  return "unchanged";
}

export function emptyFeedbackVolumeSummary(): FeedbackVolumeSummary {
  return {
    feedback_items_total: 0,
    feedback_items_valid: 0,
    feedback_items_unchanged: 0,
    feedback_items_changed: 0,
    feedback_items_invalid_or_unclassified: 0,
  };
}

export function summarizeFeedbackVolumePoints(points: FeedbackVolumePoint[]): FeedbackVolumeSummary {
  return points.reduce<FeedbackVolumeSummary>(
    (summary, point) => ({
      feedback_items_total: summary.feedback_items_total + point.feedback_items_total,
      feedback_items_valid: summary.feedback_items_valid + point.feedback_items_valid,
      feedback_items_unchanged: summary.feedback_items_unchanged + point.feedback_items_unchanged,
      feedback_items_changed: summary.feedback_items_changed + point.feedback_items_changed,
      feedback_items_invalid_or_unclassified:
        summary.feedback_items_invalid_or_unclassified + point.feedback_items_invalid_or_unclassified,
    }),
    emptyFeedbackVolumeSummary()
  );
}

export function resolveFeedbackVolumeWindow({
  days,
  startDate,
  endDate,
  now = new Date(),
}: {
  days?: number;
  startDate?: Date;
  endDate?: Date;
  now?: Date;
}): FeedbackVolumeWindow {
  if (startDate && endDate && days !== undefined) {
    throw new Error("Use either days or startDate/endDate, not both.");
  }

  if ((startDate && !endDate) || (!startDate && endDate)) {
    throw new Error("Both startDate and endDate are required for an explicit range.");
  }

  if (startDate && endDate) {
    if (endDate <= startDate) {
      throw new Error("endDate must be after startDate.");
    }
    return {
      start: new Date(startDate.getTime()),
      end: new Date(endDate.getTime()),
      label: `${startDate.toLocaleDateString()} - ${new Date(endDate.getTime() - 1).toLocaleDateString()}`,
      mode: "explicit",
    };
  }

  const resolvedDays = days ?? 90;
  if (resolvedDays <= 0) {
    throw new Error("days must be greater than zero.");
  }

  return {
    start: new Date(now.getTime() - resolvedDays * DAY_MS),
    end: new Date(now.getTime()),
    label: `Last ${resolvedDays} days`,
    mode: "days",
    days: resolvedDays,
  };
}

export function createDateWindowFromDateInputs(
  startDateInput: string,
  endDateInput: string,
  timeZone: string
): { start: Date; end: Date } {
  const start = parseDateInput(startDateInput, timeZone);
  const end = parseDateInput(endDateInput, timeZone);
  if (!start || !end) {
    throw new Error("Invalid custom date range.");
  }
  return {
    start,
    end: addZonedDays(end, 1, timeZone),
  };
}

export function parseDateInput(value: string, timeZone: string): Date | null {
  const trimmed = value.trim();
  const match = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) {
    return null;
  }
  const [, year, month, day] = match;
  return zonedPartsToDate(
    {
      year: Number(year),
      month: Number(month),
      day: Number(day),
      hour: 0,
      minute: 0,
      second: 0,
      millisecond: 0,
    },
    timeZone
  );
}

export function buildExactFeedbackVolumeBuckets({
  start,
  end,
  bucketType,
  timeZone,
  weekStart = "monday",
}: {
  start: Date;
  end: Date;
  bucketType: FeedbackVolumeBucketType;
  timeZone: string;
  weekStart?: FeedbackWeekStart;
}): TimeBucket[] {
  if (end <= start) {
    return [];
  }

  if (bucketType in TRAILING_BUCKET_DAYS) {
    const stepDays = TRAILING_BUCKET_DAYS[bucketType as keyof typeof TRAILING_BUCKET_DAYS];
    const buckets: TimeBucket[] = [];
    let currentStart = new Date(start.getTime());
    while (currentStart < end) {
      const currentEnd = new Date(Math.min(addZonedDays(currentStart, stepDays, timeZone).getTime(), end.getTime()));
      buckets.push({
        start: currentStart,
        end: currentEnd,
        label: labelForBucket(currentStart, bucketType, timeZone),
      });
      currentStart = currentEnd;
    }
    return buckets;
  }

  let periodStart = getCalendarPeriodStart(start, bucketType, timeZone, weekStart);
  const buckets: TimeBucket[] = [];

  while (periodStart < end) {
    const periodEnd = advanceCalendarPeriod(periodStart, bucketType, timeZone);
    const clippedStart = new Date(Math.max(periodStart.getTime(), start.getTime()));
    const clippedEnd = new Date(Math.min(periodEnd.getTime(), end.getTime()));
    if (clippedStart < clippedEnd) {
      buckets.push({
        start: clippedStart,
        end: clippedEnd,
        label: labelForBucket(periodStart, bucketType, timeZone),
      });
    }
    periodStart = periodEnd;
  }

  return buckets;
}

export function buildFeedbackVolumePoints(
  items: FeedbackVolumeSourceItem[],
  buckets: TimeBucket[]
): FeedbackVolumePoint[] {
  const points = buckets.map<FeedbackVolumePoint>((bucket, index) => ({
    bucket_index: index,
    label: bucket.label,
    start: bucket.start.toISOString(),
    end: bucket.end.toISOString(),
    ...emptyFeedbackVolumeSummary(),
  }));

  for (const item of items) {
    const timestamp = getFeedbackVolumeTimestamp(item);
    if (!timestamp) {
      continue;
    }

    const bucketIndex = getBucketStartIndex(timestamp, buckets);
    if (bucketIndex === -1) {
      continue;
    }

    const point = points[bucketIndex];
    point.feedback_items_total += 1;

    const classification = classifyFeedbackVolumeItem(item);
    if (classification === "invalid_or_unclassified") {
      point.feedback_items_invalid_or_unclassified += 1;
      continue;
    }

    point.feedback_items_valid += 1;
    if (classification === "changed") {
      point.feedback_items_changed += 1;
    } else {
      point.feedback_items_unchanged += 1;
    }
  }

  return points;
}

function createSeries(
  key: string,
  scope: "scorecard" | "score",
  label: string,
  items: FeedbackVolumeSourceItem[],
  buckets: TimeBucket[],
  identifiers: {
    scorecardId?: string | null;
    scorecardName?: string | null;
    scoreId?: string | null;
    scoreName?: string | null;
  } = {}
): FeedbackVolumeSeries {
  const points = buildFeedbackVolumePoints(items, buckets);
  return {
    key,
    scope,
    label,
    ...identifiers,
    points,
    summary: summarizeFeedbackVolumePoints(points),
  };
}

function sortSeries(series: FeedbackVolumeSeries[]): FeedbackVolumeSeries[] {
  return [...series].sort((left, right) => {
    const totalDiff = right.summary.feedback_items_total - left.summary.feedback_items_total;
    if (totalDiff !== 0) return totalDiff;
    return left.label.localeCompare(right.label);
  });
}

export function buildFeedbackVolumeDashboardData({
  scope,
  items,
  scorecards = [],
  scores = [],
  selectedScorecardId,
  selectedScoreId,
  timeZone,
  weekStart = "monday",
  bucketType,
  window,
}: BuildFeedbackVolumeDashboardDataInput): FeedbackVolumeDashboardData {
  const buckets = buildExactFeedbackVolumeBuckets({
    start: window.start,
    end: window.end,
    bucketType,
    timeZone,
    weekStart,
  });

  const scorecardNameById = new Map(scorecards.map((scorecard) => [scorecard.id, scorecard.name]));
  const scoreNameById = new Map(scores.map((score) => [score.id, score.name]));
  const selectedScorecardName = selectedScorecardId ? scorecardNameById.get(selectedScorecardId) || selectedScorecardId : null;
  const selectedScoreName = selectedScoreId ? scoreNameById.get(selectedScoreId) || selectedScoreId : null;

  let scopedItems = items;
  if (selectedScorecardId) {
    scopedItems = scopedItems.filter((item) => item.scorecardId === selectedScorecardId);
  }
  if (selectedScoreId) {
    scopedItems = scopedItems.filter((item) => item.scoreId === selectedScoreId);
  }

  const points = buildFeedbackVolumePoints(scopedItems, buckets);
  const summary = summarizeFeedbackVolumePoints(points);

  const scorecardSeries = scope === "account"
    ? (() => {
        const grouped = new Map<string, FeedbackVolumeSourceItem[]>();
        for (const item of scopedItems) {
          const groupKey = item.scorecardId || "__unknown_scorecard__";
          if (!grouped.has(groupKey)) grouped.set(groupKey, []);
          grouped.get(groupKey)!.push(item);
        }
        const knownIds = new Set<string>([
          ...scorecards.map((scorecard) => scorecard.id),
          ...Array.from(grouped.keys()),
        ]);
        return sortSeries(
          Array.from(knownIds).map((scorecardId) =>
            createSeries(
              `scorecard:${scorecardId}`,
              "scorecard",
              scorecardNameById.get(scorecardId) || (scorecardId === "__unknown_scorecard__" ? "Unknown Scorecard" : scorecardId),
              grouped.get(scorecardId) || [],
              buckets,
              {
                scorecardId,
                scorecardName:
                  scorecardNameById.get(scorecardId) || (scorecardId === "__unknown_scorecard__" ? "Unknown Scorecard" : scorecardId),
              }
            )
          )
        );
      })()
    : [];

  const scoreSeries = scope === "scorecard"
    ? (() => {
        const grouped = new Map<string, FeedbackVolumeSourceItem[]>();
        for (const item of scopedItems) {
          const groupKey = item.scoreId || "__unknown_score__";
          if (!grouped.has(groupKey)) grouped.set(groupKey, []);
          grouped.get(groupKey)!.push(item);
        }
        const knownIds = new Set<string>([
          ...scores.map((score) => score.id),
          ...Array.from(grouped.keys()),
        ]);
        return sortSeries(
          Array.from(knownIds).map((scoreId) =>
            createSeries(
              `score:${scoreId}`,
              "score",
              scoreNameById.get(scoreId) || (scoreId === "__unknown_score__" ? "Unknown Score" : scoreId),
              grouped.get(scoreId) || [],
              buckets,
              {
                scorecardId: selectedScorecardId,
                scorecardName: selectedScorecardName,
                scoreId,
                scoreName:
                  scoreNameById.get(scoreId) || (scoreId === "__unknown_score__" ? "Unknown Score" : scoreId),
              }
            )
          )
        );
      })()
    : [];

  return {
    scope,
    scorecard: selectedScorecardId
      ? {
          id: selectedScorecardId,
          name: selectedScorecardName || selectedScorecardId,
        }
      : null,
    score: selectedScoreId
      ? {
          id: selectedScoreId,
          name: selectedScoreName || selectedScoreId,
        }
      : null,
    summary,
    points,
    scorecardSeries,
    scoreSeries,
    dateRange: {
      start: window.start.toISOString(),
      end: window.end.toISOString(),
      label: window.label,
    },
    bucketPolicy: {
      bucket_type: bucketType,
      bucket_count: buckets.length,
      timezone: timeZone,
      week_start: weekStart,
      window_mode: "exact_window",
    },
  };
}
