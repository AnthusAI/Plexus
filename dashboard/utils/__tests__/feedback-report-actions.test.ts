import {
  buildFeedbackReportCommand,
  getFeedbackReportActions,
} from "@/utils/feedback-report-actions";

describe("feedback-report-actions", () => {
  it("exposes score-optional actions without score-only reports", () => {
    expect(getFeedbackReportActions(false).map((action) => action.id)).toEqual([
      "recent",
      "alignment",
      "timeline",
      "volume",
      "acceptance-rate",
    ]);
  });

  it("builds a 365-day volume command with calendar-month buckets", () => {
    const command = buildFeedbackReportCommand({
      actionId: "volume",
      scorecardId: "1438",
      scoreId: "45813",
      days: 365,
      timezone: "America/New_York",
      weekStart: "monday",
    });

    expect(command).toContain("feedback report volume");
    expect(command).toContain("--scorecard '1438'");
    expect(command).toContain("--score '45813'");
    expect(command).toContain("--days '365'");
    expect(command).toContain("--bucket-type 'calendar_month'");
    expect(command).toContain("--timezone 'America/New_York'");
    expect(command).toContain("--week-start 'monday'");
    expect(command).not.toContain("--background");
  });

  it("builds score-only overview and contradictions commands with explicit dates", () => {
    const overview = buildFeedbackReportCommand({
      actionId: "overview",
      scorecardId: "1438",
      scoreId: "45813",
      startDate: "2025-01-01",
      endDate: "2025-06-30",
      timezone: "America/New_York",
      weekStart: "monday",
    });

    expect(overview).toContain("feedback report overview");
    expect(overview).toContain("--start-date '2025-01-01'");
    expect(overview).toContain("--end-date '2025-06-30'");
    expect(overview).toContain("--bucket-type 'calendar_month'");

    const contradictions = buildFeedbackReportCommand({
      actionId: "contradictions",
      scorecardId: "1438",
      scoreId: "45813",
      startDate: "2025-01-01",
      endDate: "2025-06-30",
      timezone: "America/New_York",
    });

    expect(contradictions).toContain("feedback report contradictions");
    expect(contradictions).toContain("--score '45813'");
  });

  it("uses trailing_30d buckets for long acceptance-rate timelines", () => {
    const command = buildFeedbackReportCommand({
      actionId: "acceptance-rate-timeline",
      scorecardId: "1438",
      scoreId: "45813",
      days: 365,
      timezone: "America/New_York",
    });

    expect(command).toContain("feedback report acceptance-rate-timeline");
    expect(command).toContain("--bucket-type 'trailing_30d'");
  });
});
