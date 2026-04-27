import { renderHook, waitFor } from "@testing-library/react";

import { useFeedbackVolume } from "@/hooks/use-feedback-volume";
import { graphqlRequest } from "@/utils/amplify-client";
import { listFromModel } from "@/utils/amplify-helpers";

jest.mock("@/utils/amplify-client", () => ({
  graphqlRequest: jest.fn(),
}));

jest.mock("@/utils/amplify-helpers", () => ({
  listFromModel: jest.fn(),
}));

jest.mock("@/utils/data-operations", () => ({
  getClient: jest.fn(() => ({
    models: {
      Scorecard: {},
      Score: {},
    },
  })),
}));

const mockGraphqlRequest = graphqlRequest as jest.MockedFunction<typeof graphqlRequest>;
const mockListFromModel = listFromModel as jest.MockedFunction<typeof listFromModel>;

describe("useFeedbackVolume", () => {
  beforeEach(() => {
    mockGraphqlRequest.mockReset();
    mockListFromModel.mockReset();
    mockListFromModel.mockResolvedValue({
      data: [{ id: "scorecard-1", name: "SelectQuote HCS Medium-Risk" }] as never[],
      nextToken: null,
    });
  });

  it("loads account feedback volume from aggregated metrics rows", async () => {
    mockGraphqlRequest.mockResolvedValue({
      data: {
        listAggregatedMetricsByAccountIdAndRecordTypeAndTimeRangeStart: {
          items: [
            {
              accountId: "account-1",
              compositeKey: "feedbackItemsByScorecard#scorecard-1#2026-03-31T00:00:00Z#60",
              recordType: "feedbackItemsByScorecard",
              scorecardId: "scorecard-1",
              scoreId: null,
              timeRangeStart: "2026-03-31T00:00:00Z",
              timeRangeEnd: "2026-03-31T01:00:00Z",
              numberOfMinutes: 60,
              count: 3,
              metadata: {
                changedCount: 1,
                unchangedCount: 1,
                invalidCount: 1,
              },
              complete: true,
              createdAt: "2026-03-31T01:00:00Z",
              updatedAt: "2026-03-31T01:00:00Z",
            },
          ],
          nextToken: null,
        },
      },
    } as never);

    const { result } = renderHook(() =>
      useFeedbackVolume({
        accountId: "account-1",
        startDate: new Date("2026-03-30T00:00:00Z"),
        endDate: new Date("2026-04-02T00:00:00Z"),
        timezone: "UTC",
      })
    );

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeNull();
    expect(result.current.isPartial).toBe(false);
    expect(result.current.progress).toBeNull();
    expect(result.current.data?.summary.feedback_items_total).toBe(3);
    expect(result.current.data?.summary.feedback_items_changed).toBe(1);
    expect(result.current.data?.summary.feedback_items_unchanged).toBe(1);
    expect(result.current.data?.summary.feedback_items_invalid_or_unclassified).toBe(1);
    expect(result.current.data?.scorecardSeries[0]?.label).toBe("SelectQuote HCS Medium-Risk");
  });
});
