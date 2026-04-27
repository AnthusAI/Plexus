import React from "react";
import { render, screen } from "@testing-library/react";

import FeedbackVolumeTimeline from "@/components/blocks/FeedbackVolumeTimeline";

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

describe("FeedbackVolumeTimeline", () => {
  const baseProps = {
    id: "block-1",
    config: {},
    output: {
      block_title: "Feedback Volume Timeline",
      block_description: "Feedback item volume over time",
      scorecard_name: "Scorecard A",
      score_name: "Score A",
      points: [
        {
          bucket_index: 0,
          label: "2026-04-01",
          start: "2026-04-01T00:00:00+00:00",
          end: "2026-04-08T00:00:00+00:00",
          feedback_items_total: 10,
          feedback_items_valid: 9,
          feedback_items_unchanged: 7,
          feedback_items_changed: 2,
          feedback_items_invalid_or_unclassified: 1,
        },
      ],
      summary: {
        feedback_items_total: 10,
        feedback_items_valid: 9,
        feedback_items_unchanged: 7,
        feedback_items_changed: 2,
        feedback_items_invalid_or_unclassified: 1,
      },
      show_bucket_details: false,
    },
    log: undefined,
    name: "Feedback Volume Timeline",
    position: 1,
    type: "FeedbackVolumeTimeline",
    attachedFiles: [],
  };

  it("renders chart-first summary and hides bucket details by default", () => {
    render(<FeedbackVolumeTimeline {...baseProps} />);

    expect(screen.getByText("Feedback Volume Timeline")).toBeInTheDocument();
    expect(screen.getByText("Total Feedback Items")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByTestId("chart-container")).toBeInTheDocument();
    expect(screen.queryByText("Bucket Metrics")).not.toBeInTheDocument();
  });

  it("renders bucket details when enabled", () => {
    render(
      <FeedbackVolumeTimeline
        {...baseProps}
        output={{
          ...(baseProps.output as any),
          show_bucket_details: true,
        }}
      />
    );

    expect(screen.getByText("Bucket Metrics")).toBeInTheDocument();
    expect(screen.getAllByText("Invalid / Unclassified")).toHaveLength(2);
  });

  it("shows processing placeholder instead of zero metrics while pending", () => {
    render(
      <FeedbackVolumeTimeline
        {...baseProps}
        config={{ isProcessing: true }}
        output={{ block_title: "Feedback Volume Timeline", points: [] }}
      />
    );

    expect(screen.getByText(/Report block is processing/)).toBeInTheDocument();
    expect(screen.queryByText("Bucket Metrics")).not.toBeInTheDocument();
  });
});
