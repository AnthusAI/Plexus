export type FeedbackReportActionId =
  | "recent"
  | "analysis"
  | "timeline"
  | "volume"
  | "acceptance-rate"
  | "contradictions"
  | "acceptance-rate-timeline"
  | "overview";

export interface FeedbackReportActionDefinition {
  id: FeedbackReportActionId;
  label: string;
  requiresScore: boolean;
}

export interface FeedbackReportWindowParams {
  days?: number;
  startDate?: string | null;
  endDate?: string | null;
  timezone: string;
  weekStart?: "monday" | "sunday";
}

export interface BuildFeedbackReportCommandInput extends FeedbackReportWindowParams {
  actionId: FeedbackReportActionId;
  scorecardId: string;
  scoreId?: string | null;
}

const SCORE_OPTIONAL_ACTIONS: FeedbackReportActionDefinition[] = [
  { id: "recent", label: "Recent Feedback", requiresScore: false },
  { id: "analysis", label: "Feedback Analysis", requiresScore: false },
  { id: "timeline", label: "Feedback Alignment Timeline", requiresScore: false },
  { id: "volume", label: "Feedback Volume Timeline", requiresScore: false },
  { id: "acceptance-rate", label: "Acceptance Rate", requiresScore: false },
];

const SCORE_REQUIRED_ACTIONS: FeedbackReportActionDefinition[] = [
  { id: "contradictions", label: "Feedback Contradictions", requiresScore: true },
  { id: "acceptance-rate-timeline", label: "Acceptance Rate Timeline", requiresScore: true },
  { id: "overview", label: "Feedback Overview", requiresScore: true },
];

function shellQuote(value: string): string {
  return `'${value.replace(/'/g, `'\"'\"'`)}'`;
}

function resolveWindowFlagParts({
  days,
  startDate,
  endDate,
}: Pick<FeedbackReportWindowParams, "days" | "startDate" | "endDate">): string[] {
  if (days !== undefined && days !== null) {
    return ["--days", String(days)];
  }

  if (startDate && endDate) {
    return ["--start-date", startDate, "--end-date", endDate];
  }

  return ["--days", "90"];
}

function resolveTimelineBucketType({
  days,
  startDate,
  endDate,
}: Pick<FeedbackReportWindowParams, "days" | "startDate" | "endDate">): "calendar_week" | "calendar_month" {
  if (days !== undefined && days !== null) {
    return days > 180 ? "calendar_month" : "calendar_week";
  }

  if (startDate && endDate) {
    const start = new Date(`${startDate}T00:00:00Z`);
    const end = new Date(`${endDate}T00:00:00Z`);
    const spanDays = Math.max(1, Math.ceil((end.getTime() - start.getTime()) / (24 * 60 * 60 * 1000)) + 1);
    return spanDays > 180 ? "calendar_month" : "calendar_week";
  }

  return "calendar_week";
}

function resolveAcceptanceTimelineBucketType({
  days,
  startDate,
  endDate,
}: Pick<FeedbackReportWindowParams, "days" | "startDate" | "endDate">): "trailing_7d" | "trailing_30d" {
  if (days !== undefined && days !== null) {
    return days > 180 ? "trailing_30d" : "trailing_7d";
  }

  if (startDate && endDate) {
    const start = new Date(`${startDate}T00:00:00Z`);
    const end = new Date(`${endDate}T00:00:00Z`);
    const spanDays = Math.max(1, Math.ceil((end.getTime() - start.getTime()) / (24 * 60 * 60 * 1000)) + 1);
    return spanDays > 180 ? "trailing_30d" : "trailing_7d";
  }

  return "trailing_7d";
}

function stringifyCommand(parts: Array<string | undefined | null | false>): string {
  let seenFlag = false;

  return parts
    .filter((part): part is string => Boolean(part))
    .map((part) => {
      if (part.startsWith("--")) {
        seenFlag = true;
        return part;
      }
      if (!seenFlag) {
        return part;
      }
      return shellQuote(part);
    })
    .join(" ");
}

export function getFeedbackReportActions(scoreSelected: boolean): FeedbackReportActionDefinition[] {
  return scoreSelected ? [...SCORE_OPTIONAL_ACTIONS, ...SCORE_REQUIRED_ACTIONS] : [...SCORE_OPTIONAL_ACTIONS];
}

export function buildFeedbackReportCommand({
  actionId,
  scorecardId,
  scoreId,
  days,
  startDate,
  endDate,
  timezone,
  weekStart = "monday",
}: BuildFeedbackReportCommandInput): string {
  const baseParts = ["feedback", "report", actionId, "--scorecard", scorecardId];
  const scoreParts = scoreId ? ["--score", scoreId] : [];
  const windowParts = resolveWindowFlagParts({ days, startDate, endDate });

  switch (actionId) {
    case "recent":
    case "analysis":
      return stringifyCommand([...baseParts, ...scoreParts, ...windowParts]);

    case "acceptance-rate":
      return stringifyCommand([...baseParts, ...scoreParts, ...windowParts, "--max-items", "200"]);

    case "timeline":
    case "volume": {
      const bucketType = resolveTimelineBucketType({ days, startDate, endDate });
      return stringifyCommand([
        ...baseParts,
        ...scoreParts,
        ...windowParts,
        "--bucket-type",
        bucketType,
        "--timezone",
        timezone,
        "--week-start",
        weekStart,
      ]);
    }

    case "acceptance-rate-timeline": {
      if (!scoreId) {
        throw new Error("acceptance-rate-timeline requires a scoreId");
      }
      const bucketType = resolveAcceptanceTimelineBucketType({ days, startDate, endDate });
      return stringifyCommand([
        ...baseParts,
        "--score",
        scoreId,
        ...windowParts,
        "--bucket-type",
        bucketType,
      ]);
    }

    case "contradictions":
      if (!scoreId) {
        throw new Error("contradictions requires a scoreId");
      }
      return stringifyCommand([...baseParts, "--score", scoreId, ...windowParts]);

    case "overview": {
      if (!scoreId) {
        throw new Error("overview requires a scoreId");
      }
      const bucketType = resolveTimelineBucketType({ days, startDate, endDate });
      return stringifyCommand([
        ...baseParts,
        "--score",
        scoreId,
        ...windowParts,
        "--bucket-type",
        bucketType,
        "--timezone",
        timezone,
        "--week-start",
        weekStart,
      ]);
    }

    default:
      throw new Error(`Unsupported feedback report action: ${actionId}`);
  }
}
