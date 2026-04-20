import {
  buildFeedbackVolumeDashboardData,
  classifyFeedbackVolumeItem,
  createDateWindowFromDateInputs,
  pickAutoFeedbackVolumeBucketType,
  type FeedbackVolumeSourceItem,
} from "@/utils/feedback-volume";

describe("feedback-volume utilities", () => {
  it("classifies changed, unchanged, and invalid feedback items", () => {
    expect(
      classifyFeedbackVolumeItem({
        id: "1",
        initialAnswerValue: "yes",
        finalAnswerValue: "no",
      })
    ).toBe("changed");

    expect(
      classifyFeedbackVolumeItem({
        id: "2",
        initialAnswerValue: "yes",
        finalAnswerValue: "yes",
      })
    ).toBe("unchanged");

    expect(
      classifyFeedbackVolumeItem({
        id: "3",
        initialAnswerValue: "yes",
        isInvalid: true,
      })
    ).toBe("invalid_or_unclassified");
  });

  it("chooses day, week, and month bucket defaults from the window size", () => {
    const start = new Date("2026-01-01T00:00:00Z");

    expect(pickAutoFeedbackVolumeBucketType(start, new Date("2026-01-10T00:00:00Z"))).toBe("calendar_day");
    expect(pickAutoFeedbackVolumeBucketType(start, new Date("2026-03-20T00:00:00Z"))).toBe("calendar_week");
    expect(pickAutoFeedbackVolumeBucketType(start, new Date("2026-12-31T00:00:00Z"))).toBe("calendar_month");
  });

  it("builds scorecard scope data with zero-feedback scores preserved", () => {
    const window = createDateWindowFromDateInputs("2026-01-01", "2026-01-07", "UTC");
    const items: FeedbackVolumeSourceItem[] = [
      {
        id: "feedback-1",
        scorecardId: "scorecard-1",
        scoreId: "score-1",
        initialAnswerValue: "yes",
        finalAnswerValue: "no",
        editedAt: "2026-01-02T12:00:00Z",
      },
      {
        id: "feedback-2",
        scorecardId: "scorecard-1",
        scoreId: "score-1",
        initialAnswerValue: "yes",
        finalAnswerValue: "yes",
        editedAt: "2026-01-03T12:00:00Z",
      },
    ];

    const data = buildFeedbackVolumeDashboardData({
      scope: "scorecard",
      items,
      scorecards: [{ id: "scorecard-1", name: "Medium Risk" }],
      scores: [
        { id: "score-1", name: "Agent Misrepresentation" },
        { id: "score-2", name: "Good Call" },
      ],
      selectedScorecardId: "scorecard-1",
      bucketType: "calendar_day",
      timeZone: "UTC",
      window: {
        start: window.start,
        end: window.end,
        label: "2026-01-01 - 2026-01-07",
        mode: "explicit",
      },
    });

    expect(data.scope).toBe("scorecard");
    expect(data.summary.feedback_items_total).toBe(2);
    expect(data.summary.feedback_items_changed).toBe(1);
    expect(data.scoreSeries).toHaveLength(2);
    expect(data.scoreSeries[0].label).toBe("Agent Misrepresentation");
    expect(data.scoreSeries[0].summary.feedback_items_total).toBe(2);
    expect(data.scoreSeries[1].label).toBe("Good Call");
    expect(data.scoreSeries[1].summary.feedback_items_total).toBe(0);
  });

  it("builds account scope data with scorecards sorted by feedback volume", () => {
    const window = createDateWindowFromDateInputs("2026-01-01", "2026-01-31", "UTC");
    const items: FeedbackVolumeSourceItem[] = [
      {
        id: "feedback-a",
        scorecardId: "scorecard-2",
        scoreId: "score-a",
        initialAnswerValue: "yes",
        finalAnswerValue: "no",
        editedAt: "2026-01-15T12:00:00Z",
      },
      {
        id: "feedback-b",
        scorecardId: "scorecard-2",
        scoreId: "score-a",
        initialAnswerValue: "yes",
        finalAnswerValue: "yes",
        editedAt: "2026-01-18T12:00:00Z",
      },
      {
        id: "feedback-c",
        scorecardId: "scorecard-1",
        scoreId: "score-b",
        initialAnswerValue: "yes",
        finalAnswerValue: "yes",
        editedAt: "2026-01-19T12:00:00Z",
      },
    ];

    const data = buildFeedbackVolumeDashboardData({
      scope: "account",
      items,
      scorecards: [
        { id: "scorecard-1", name: "Small Queue" },
        { id: "scorecard-2", name: "Large Queue" },
        { id: "scorecard-3", name: "Empty Queue" },
      ],
      bucketType: "calendar_week",
      timeZone: "UTC",
      window: {
        start: window.start,
        end: window.end,
        label: "2026-01-01 - 2026-01-31",
        mode: "explicit",
      },
    });

    expect(data.scorecardSeries.map((series) => series.label)).toEqual([
      "Large Queue",
      "Small Queue",
      "Empty Queue",
    ]);
    expect(data.scorecardSeries[0].summary.feedback_items_total).toBe(2);
    expect(data.scorecardSeries[2].summary.feedback_items_total).toBe(0);
  });
});
