import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import FeedbackDashboard from "@/components/feedback-dashboard";
import { useFeedbackVolume } from "@/hooks/use-feedback-volume";

jest.mock("@/app/contexts/AccountContext", () => ({
  useAccount: () => ({
    selectedAccount: { id: "account-1", name: "Test Account" },
    isLoadingAccounts: false,
  }),
}));

jest.mock("@/components/ScorecardContext", () => () => <div data-testid="scorecard-context" />);

jest.mock("@/components/ui/chart", () => ({
  ChartContainer: ({ children }: any) => <div data-testid="chart-container">{children}</div>,
}));

jest.mock("recharts", () => ({
  Bar: () => null,
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  CartesianGrid: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

jest.mock("@/utils/data-operations", () => ({
  createTask: jest.fn(),
}));

jest.mock("@/components/blocks/useIncrementalRows", () => ({
  useIncrementalRows: (rows: any[]) => ({
    visibleRows: rows,
    visibleCount: rows.length,
    totalCount: rows.length,
    hasMore: false,
    loadMore: jest.fn(),
    sentinelRef: { current: null },
  }),
}));

jest.mock("@/hooks/use-feedback-volume", () => ({
  useFeedbackVolume: jest.fn(),
}));

const mockUseFeedbackVolume = useFeedbackVolume as jest.MockedFunction<typeof useFeedbackVolume>;

const accountData = {
  scope: "account" as const,
  scorecard: null,
  score: null,
  summary: {
    feedback_items_total: 3,
    feedback_items_valid: 3,
    feedback_items_unchanged: 2,
    feedback_items_changed: 1,
    feedback_items_invalid_or_unclassified: 0,
  },
  points: [
    {
      bucket_index: 0,
      label: "2026-01-01",
      start: "2026-01-01T00:00:00Z",
      end: "2026-01-08T00:00:00Z",
      feedback_items_total: 3,
      feedback_items_valid: 3,
      feedback_items_unchanged: 2,
      feedback_items_changed: 1,
      feedback_items_invalid_or_unclassified: 0,
    },
  ],
  scorecardSeries: [
    {
      key: "scorecard:scorecard-1",
      scope: "scorecard" as const,
      label: "SelectQuote HCS Medium-Risk",
      scorecardId: "scorecard-1",
      scorecardName: "SelectQuote HCS Medium-Risk",
      points: [
        {
          bucket_index: 0,
          label: "2026-01-01",
          start: "2026-01-01T00:00:00Z",
          end: "2026-01-08T00:00:00Z",
          feedback_items_total: 3,
          feedback_items_valid: 3,
          feedback_items_unchanged: 2,
          feedback_items_changed: 1,
          feedback_items_invalid_or_unclassified: 0,
        },
      ],
      summary: {
        feedback_items_total: 3,
        feedback_items_valid: 3,
        feedback_items_unchanged: 2,
        feedback_items_changed: 1,
        feedback_items_invalid_or_unclassified: 0,
      },
    },
  ],
  scoreSeries: [],
  dateRange: {
    start: "2026-01-01T00:00:00Z",
    end: "2026-04-01T00:00:00Z",
    label: "Last 90 days",
  },
  bucketPolicy: {
    bucket_type: "calendar_week" as const,
    bucket_count: 12,
    timezone: "UTC",
    week_start: "monday" as const,
    window_mode: "exact_window" as const,
  },
};

const scorecardData = {
  ...accountData,
  scope: "scorecard" as const,
  scorecard: { id: "scorecard-1", name: "SelectQuote HCS Medium-Risk" },
  scorecardSeries: [],
  scoreSeries: [
    {
      key: "score:score-1",
      scope: "score" as const,
      label: "Agent Misrepresentation",
      scorecardId: "scorecard-1",
      scorecardName: "SelectQuote HCS Medium-Risk",
      scoreId: "score-1",
      scoreName: "Agent Misrepresentation",
      points: accountData.points,
      summary: accountData.summary,
    },
  ],
};

const scoreData = {
  ...scorecardData,
  scope: "score" as const,
  score: { id: "score-1", name: "Agent Misrepresentation" },
  scoreSeries: [],
};

describe("FeedbackDashboard", () => {
  beforeEach(() => {
    mockUseFeedbackVolume.mockImplementation((config) => {
      if (config.scoreId === "score-1") {
        return { isLoading: false, error: null, data: scoreData };
      }
      if (config.scorecardId === "scorecard-1") {
        return { isLoading: false, error: null, data: scorecardData };
      }
      return { isLoading: false, error: null, data: accountData };
    });
  });

  afterEach(() => {
    mockUseFeedbackVolume.mockReset();
  });

  it("drills from account scorecards into scorecard and score views", () => {
    render(<FeedbackDashboard />);

    expect(screen.getByText("Scorecards")).toBeInTheDocument();
    expect(screen.getByText("SelectQuote HCS Medium-Risk")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /open/i }));

    expect(screen.getByText("Scores")).toBeInTheDocument();
    expect(screen.getByText("Agent Misrepresentation")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: /open/i })[0]);

    expect(screen.getByRole("button", { name: /Clear score/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run score report/i })).toBeInTheDocument();
  });
});
