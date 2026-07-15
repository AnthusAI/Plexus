import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import FeedbackAlignmentTimeline from "@/components/blocks/FeedbackAlignmentTimeline";

jest.mock("@/components/ui/chart", () => ({
  ChartContainer: ({ children }: any) => <div data-testid="chart-container">{children}</div>,
}));

jest.mock("recharts", () => ({
  CartesianGrid: () => null,
  Line: () => null,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  ReferenceArea: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

jest.mock("@/components/blocks/ReportBlock", () => {
  const MockReportBlock = ({ title, children }: any) => (
    <div>
      <div>{title}</div>
      {children}
    </div>
  );
  return {
    __esModule: true,
    default: MockReportBlock,
  };
});

const mockDownloadData = jest.fn();
jest.mock("aws-amplify/storage", () => ({
  downloadData: (...args: any[]) => mockDownloadData(...args),
}));

describe("FeedbackAlignmentTimeline", () => {
  const baseProps = {
    id: "block-1",
    config: {},
    output: {
      mode: "all_scores",
      block_title: "Feedback Alignment Timeline",
      block_description: "Alignment metrics over time",
      bucket_policy: {
        bucket_type: "calendar_month",
        bucket_count: 2,
        timezone: "UTC",
        week_start: "monday",
        complete_only: false,
        window_mode: "exact_window",
      },
      sample_policy: {
        rolling_min_items: 100,
      },
      fetched_feedback_items: 240,
      ignored_invalid_feedback_items: 12,
      analyzed_feedback_items: 228,
      overall: {
        score_id: "overall",
        score_name: "Overall",
        points: [
          {
            bucket_index: 0,
            label: "2026-01",
            start: "2026-01-01T00:00:00+00:00",
            end: "2026-02-01T00:00:00+00:00",
            ac1: 0.7,
            accuracy: 80,
            item_count: 100,
            bucket_item_count: 40,
            sample_item_count: 100,
            lookback_item_count: 60,
            sample_start: "2025-12-10T00:00:00+00:00",
            sample_end: "2026-01-30T00:00:00+00:00",
            sample_extended: true,
            agreements: 80,
            mismatches: 20,
          },
        ],
      },
      scores: [
        {
          score_id: "score-1",
          score_name: "Score One",
          points: [
            {
              bucket_index: 0,
              label: "2026-01",
              start: "2026-01-01T00:00:00+00:00",
              end: "2026-02-01T00:00:00+00:00",
              ac1: 0.75,
              accuracy: 82,
              item_count: 100,
              bucket_item_count: 100,
              sample_item_count: 100,
              lookback_item_count: 0,
              sample_start: "2026-01-01T00:00:00+00:00",
              sample_end: "2026-01-30T00:00:00+00:00",
              sample_extended: false,
              agreements: 82,
              mismatches: 18,
            },
          ],
        },
        {
          score_id: "score-2",
          score_name: "Score Two",
          points: [
            {
              bucket_index: 0,
              label: "2026-01",
              start: "2026-01-01T00:00:00+00:00",
              end: "2026-02-01T00:00:00+00:00",
              ac1: 0.62,
              accuracy: 74,
              item_count: 75,
              bucket_item_count: 20,
              sample_item_count: 75,
              lookback_item_count: 55,
              sample_start: "2025-11-20T00:00:00+00:00",
              sample_end: "2026-01-29T00:00:00+00:00",
              sample_extended: true,
              agreements: 56,
              mismatches: 19,
            },
          ],
        },
      ],
      show_bucket_details: true,
    },
    log: undefined,
    name: "Feedback Alignment Timeline",
    position: 1,
    type: "FeedbackAlignmentTimeline",
    attachedFiles: [],
  };

  it("renders explanation copy and one chart per overall and score series", () => {
    render(<FeedbackAlignmentTimeline {...baseProps} />);

    expect(screen.getByText("What these charts measure")).toBeInTheDocument();
    expect(screen.getByText(/stored production score answers agreed/)).toBeInTheDocument();
    expect(screen.getByText(/feedback was edited, not when the call happened/)).toBeInTheDocument();
    expect(screen.getByText(/not a replay or backtest of historical champion versions/)).toBeInTheDocument();
    expect(screen.getByText("Overall")).toBeInTheDocument();
    expect(screen.getByText("Score One")).toBeInTheDocument();
    expect(screen.getByText("Score Two")).toBeInTheDocument();
    expect(screen.getByText(/Ignored invalid feedback items: 12/)).toBeInTheDocument();
    expect(screen.getAllByTestId("chart-container")).toHaveLength(3);
  });

  it("hides methodology copy when the split score block disables it", () => {
    render(
      <FeedbackAlignmentTimeline
        {...baseProps}
        output={{
          ...baseProps.output,
          show_methodology: false,
        }}
      />
    );

    expect(screen.queryByText("What these charts measure")).not.toBeInTheDocument();
    expect(screen.queryByText(/stored production score answers agreed/)).not.toBeInTheDocument();
    expect(screen.getAllByTestId("chart-container")).toHaveLength(3);
  });

  it("does not render bucket gauge details even when legacy flag is true", () => {
    render(<FeedbackAlignmentTimeline {...baseProps} />);

    expect(screen.queryByText("Bucket Details")).not.toBeInTheDocument();
    expect(screen.queryByText("Raw Agreement")).not.toBeInTheDocument();
  });

  it("renders rolling sample metadata for extended points", () => {
    render(<FeedbackAlignmentTimeline {...baseProps} />);

    expect(screen.getAllByText("Lookback used").length).toBeGreaterThan(0);
    expect(screen.getAllByText("100 sampled items").length).toBeGreaterThan(0);
    expect(screen.getByText("75 sampled items")).toBeInTheDocument();
  });

  it("reloads compacted output when attachment path changes between blocks", async () => {
    mockDownloadData.mockImplementation(({ path }: { path: string }) => {
      const payloadByPath: Record<string, any> = {
        "reportblocks/block-1/output-block-1.json": {
          block_title: "Score A Alignment Timeline",
          block_description: "Stored feedback alignment for this score.",
          mode: "single_score",
          overall: {
            score_id: "score-a",
            score_name: "Score A",
            points: [
              { bucket_index: 0, label: "2026-01", ac1: 0.5, accuracy: 50, item_count: 10 },
            ],
          },
          scores: [],
          bucket_policy: {
            bucket_type: "calendar_month",
            bucket_count: 1,
            timezone: "UTC",
            week_start: "monday",
            complete_only: false,
            window_mode: "exact_window",
          },
          sample_policy: { rolling_min_items: 100 },
        },
        "reportblocks/block-2/output-block-2.json": {
          block_title: "Score B Alignment Timeline",
          block_description: "Stored feedback alignment for this score.",
          mode: "single_score",
          overall: {
            score_id: "score-b",
            score_name: "Score B",
            points: [
              { bucket_index: 0, label: "2026-01", ac1: 0.9, accuracy: 90, item_count: 10 },
            ],
          },
          scores: [],
          bucket_policy: {
            bucket_type: "calendar_month",
            bucket_count: 1,
            timezone: "UTC",
            week_start: "monday",
            complete_only: false,
            window_mode: "exact_window",
          },
          sample_policy: { rolling_min_items: 100 },
        },
      };
      return {
        result: Promise.resolve({
          body: {
            text: async () => JSON.stringify(payloadByPath[path]),
          },
        }),
      };
    });

    const { rerender } = render(
      <FeedbackAlignmentTimeline
        {...baseProps}
        id="block-1"
        output={{
          output_compacted: true,
          output_attachment: "reportblocks/block-1/output-block-1.json",
        }}
        name="Score A Alignment Timeline"
      />
    );

    await waitFor(() =>
      expect(screen.getByText("Score A Alignment Timeline")).toBeInTheDocument()
    );

    rerender(
      <FeedbackAlignmentTimeline
        {...baseProps}
        id="block-2"
        output={{
          output_compacted: true,
          output_attachment: "reportblocks/block-2/output-block-2.json",
        }}
        name="Score B Alignment Timeline"
      />
    );

    await waitFor(() =>
      expect(screen.getByText("Score B Alignment Timeline")).toBeInTheDocument()
    );
    expect(screen.queryByText("Score A Alignment Timeline")).not.toBeInTheDocument();
    expect(mockDownloadData).toHaveBeenCalledTimes(2);
  });
});
