import { act, renderHook, waitFor } from "@testing-library/react";

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

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (error: unknown) => void;
};

function createDeferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((innerResolve, innerReject) => {
    resolve = innerResolve;
    reject = innerReject;
  });
  return { promise, resolve, reject };
}

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

  it("publishes partial account snapshots while unioning editedAt and updatedAt pages", async () => {
    const editedPageOne = createDeferred<any>();
    const editedPageTwo = createDeferred<any>();
    const updatedPageOne = createDeferred<any>();

    mockGraphqlRequest
      .mockImplementationOnce(() => editedPageOne.promise)
      .mockImplementationOnce(() => editedPageTwo.promise)
      .mockImplementationOnce(() => updatedPageOne.promise);

    const { result } = renderHook(() =>
      useFeedbackVolume({
        accountId: "account-1",
        days: 90,
        timezone: "UTC",
      })
    );

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeNull();

    await act(async () => {
      editedPageOne.resolve({
        data: {
          listFeedbackItemByAccountIdAndEditedAt: {
            items: [
              {
                id: "feedback-1",
                scorecardId: "scorecard-1",
                scoreId: "score-1",
                initialAnswerValue: "yes",
                finalAnswerValue: "no",
                editedAt: "2026-03-02T00:00:00Z",
              },
            ],
            nextToken: "edited-next",
          },
        },
      });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
      expect(result.current.isPartial).toBe(true);
      expect(result.current.progress?.phase).toBe("fetching_edited");
      expect(result.current.progress?.pagesFetched).toBe(1);
      expect(result.current.progress?.rawCount).toBe(1);
      expect(result.current.progress?.uniqueCount).toBe(1);
      expect(result.current.data?.summary.feedback_items_total).toBe(1);
    });

    await act(async () => {
      editedPageTwo.resolve({
        data: {
          listFeedbackItemByAccountIdAndEditedAt: {
            items: [
              {
                id: "feedback-2",
                scorecardId: "scorecard-1",
                scoreId: "score-2",
                initialAnswerValue: "yes",
                finalAnswerValue: "yes",
                editedAt: "2026-03-03T00:00:00Z",
              },
            ],
            nextToken: null,
          },
        },
      });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.progress?.pagesFetched).toBe(2);
      expect(result.current.progress?.rawCount).toBe(2);
      expect(result.current.progress?.uniqueCount).toBe(2);
      expect(result.current.data?.summary.feedback_items_total).toBe(2);
    });

    await act(async () => {
      updatedPageOne.resolve({
        data: {
          listFeedbackItemByAccountIdAndUpdatedAt: {
            items: [
              {
                id: "feedback-1",
                scorecardId: "scorecard-1",
                scoreId: "score-1",
                initialAnswerValue: "yes",
                finalAnswerValue: "no",
                updatedAt: "2026-03-04T00:00:00Z",
              },
              {
                id: "feedback-3",
                scorecardId: "scorecard-1",
                scoreId: "score-3",
                initialAnswerValue: "yes",
                finalAnswerValue: null,
                updatedAt: "2026-03-05T00:00:00Z",
              },
            ],
            nextToken: null,
          },
        },
      });
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.isPartial).toBe(false);
      expect(result.current.progress).toBeNull();
      expect(result.current.error).toBeNull();
      expect(result.current.data?.summary.feedback_items_total).toBe(3);
      expect(result.current.data?.summary.feedback_items_changed).toBe(1);
      expect(result.current.data?.summary.feedback_items_unchanged).toBe(1);
      expect(result.current.data?.summary.feedback_items_invalid_or_unclassified).toBe(1);
    });
  });
});
