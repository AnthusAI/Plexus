import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

import ScoreChampionVersionTimeline from "@/components/blocks/ScoreChampionVersionTimeline";

const mockDownloadData = jest.fn();

jest.mock("aws-amplify/storage", () => ({
  downloadData: (...args: any[]) => mockDownloadData(...args),
}));

jest.mock("@monaco-editor/react", () => ({
  DiffEditor: ({ language, original, modified }: any) => (
    <div data-testid={`diff-editor-${language}`} data-original={original} data-modified={modified} />
  ),
}));

jest.mock("@/components/ui/chart", () => ({
  ChartContainer: ({ children }: any) => <div data-testid="chart-container">{children}</div>,
}));

jest.mock("@/components/ui/tabs", () => ({
  Tabs: ({ children }: any) => <div>{children}</div>,
  TabsContent: ({ children }: any) => <div>{children}</div>,
  TabsList: ({ children }: any) => <div>{children}</div>,
  TabsTrigger: ({ children }: any) => <button>{children}</button>,
}));

jest.mock("recharts", () => ({
  CartesianGrid: () => null,
  Line: ({ dataKey }: any) => <div data-testid={`line-${dataKey}`} />,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Tooltip: () => null,
  XAxis: ({ domain }: any) => <div data-testid="x-axis" data-domain={Array.isArray(domain) ? domain.join(",") : ""} />,
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

describe("ScoreChampionVersionTimeline", () => {
  beforeEach(() => {
    mockDownloadData.mockReset();
  });

  const output = {
    report_type: "score_champion_version_timeline",
    block_title: "Score Champion Version Timeline",
    block_description: "Champion changes",
    scorecard_name: "Scorecard A",
    date_range: {
      start: "2026-04-01T00:00:00+00:00",
      end: "2026-04-30T23:59:59+00:00",
    },
    summary: {
      scores_analyzed: 2,
      scores_with_champion_changes: 2,
      champion_change_count: 2,
      procedure_count: 3,
      evaluation_count: 4,
      score_result_count: 120,
      optimization_cost: { overall: 2.5, inference: 0.5, evaluation: 2.0 },
      associated_evaluation_cost: 1.25,
      evaluations_scanned: 1,
    },
    scores: [
      {
        score_id: "score-1",
        score_name: "Score 1",
        optimization_summary: {
          procedure_count: 1,
          evaluation_count: 1,
          score_result_count: 25,
          optimization_cost: { overall: 1.5, inference: 0.4, evaluation: 1.1 },
          associated_evaluation_cost: 0.5,
        },
        sme: {
          procedure_id: "procedure-1",
          procedure_status: "COMPLETED",
          procedure_updated_at: "2026-04-11T01:00:00+00:00",
          available: true,
          agenda: "Review boundary cases with the SME.",
          worksheet: "Confirm the transfer criteria.",
          generated_at: "2026-04-11T02:00:00+00:00",
        },
        points: [
          {
            point_index: 0,
            label: "2026-04-10",
            entered_at: "2026-04-10T12:00:00+00:00",
            version_id: "version-1",
            previous_champion_version_id: "version-0",
            feedback_evaluation_id: "eval-feedback",
            feedback_metrics: {
              alignment: 0.82,
              accuracy: 84,
              evaluation_id: "eval-feedback",
            },
            regression_evaluation_id: null,
            regression_metrics: null,
          },
        ],
        diff: {
          left_version_id: "version-0",
          right_version_id: "version-1",
          configuration_left: "name: old",
          configuration_right: "name: new",
          configuration_diff: "--- version-0/configuration\n+++ version-1/configuration\n-name: old\n+name: new",
          guidelines_left: "Old guideline",
          guidelines_right: "New guideline",
          guidelines_diff: "--- version-0/guidelines\n+++ version-1/guidelines\n-Old guideline\n+New guideline",
        },
      },
      {
        score_id: "score-2",
        score_name: "Score 2",
        optimization_summary: {
          procedure_count: 2,
          evaluation_count: 3,
          score_result_count: 95,
          optimization_cost: { overall: 1.0, inference: 0.1, evaluation: 0.9 },
          associated_evaluation_cost: 0.75,
        },
        points: [
          {
            point_index: 0,
            label: "2026-04-20",
            entered_at: "2026-04-20T12:00:00+00:00",
            version_id: "version-2",
            previous_champion_version_id: "version-1",
            feedback_evaluation_id: null,
            feedback_metrics: null,
            regression_evaluation_id: null,
            regression_metrics: null,
          },
        ],
        diff: {
          left_version_id: "version-1",
          right_version_id: "version-2",
          configuration_diff: null,
          guidelines_diff: null,
        },
      },
    ],
  };

  const baseProps = {
    id: "block-1",
    config: {},
    output,
    log: undefined,
    name: "Score Champion Version Timeline",
    position: 1,
    type: "ScoreChampionVersionTimeline",
    attachedFiles: [],
  };

  it("renders every score separately with available dataset series only", () => {
    render(<ScoreChampionVersionTimeline {...baseProps} />);

    expect(screen.getByText("Score Champion Version Timeline")).toBeInTheDocument();
    expect(screen.getByText("Score 1")).toBeInTheDocument();
    expect(screen.getByText("Score 2")).toBeInTheDocument();
    expect(screen.getByText("$2.50")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("$1.50")).toBeInTheDocument();
    expect(screen.getByText("$1.00")).toBeInTheDocument();
    expect(screen.getAllByTestId("chart-container")).toHaveLength(2);
    expect(screen.getAllByTestId("line-timeline_marker")).toHaveLength(2);
    expect(screen.getByTestId("line-feedback_alignment")).toBeInTheDocument();
    expect(screen.getByTestId("line-feedback_accuracy")).toBeInTheDocument();
    expect(screen.queryByTestId("line-regression_alignment")).not.toBeInTheDocument();
    expect(screen.queryByTestId("line-regression_accuracy")).not.toBeInTheDocument();
    expect(screen.queryByText("Select score")).not.toBeInTheDocument();
  });

  it("uses the same x-axis date range for each score chart", () => {
    render(<ScoreChampionVersionTimeline {...baseProps} />);

    const expectedDomain = [
      new Date(output.date_range.start).getTime(),
      new Date(output.date_range.end).getTime(),
    ].join(",");
    expect(screen.getAllByTestId("x-axis").map((axis) => axis.getAttribute("data-domain"))).toEqual([
      expectedDomain,
      expectedDomain,
    ]);
  });

  it("shows an empty state when there are no champion changes", () => {
    render(
      <ScoreChampionVersionTimeline
        {...baseProps}
        output={{
          ...output,
          scores: [],
          summary: {
            scores_analyzed: 1,
            scores_with_champion_changes: 0,
            champion_change_count: 0,
            evaluations_scanned: 0,
          },
          message: "No champion version changes found in the requested time window.",
        }}
      />
    );

    expect(screen.getByText("No champion version changes found in the requested time window.")).toBeInTheDocument();
    expect(screen.queryByTestId("chart-container")).not.toBeInTheDocument();
  });

  it("renders code and guidelines in Monaco diff editors", () => {
    render(<ScoreChampionVersionTimeline {...baseProps} />);

    expect(screen.getAllByText("Champion Diff")).toHaveLength(2);
    expect(screen.getAllByText("Code")).toHaveLength(2);
    expect(screen.getAllByText("Guidelines")).toHaveLength(2);
    const codeDiff = screen.getByTestId("diff-editor-yaml");
    const guidelinesDiff = screen.getByTestId("diff-editor-markdown");
    expect(codeDiff).toHaveAttribute("data-original", "name: old");
    expect(codeDiff).toHaveAttribute("data-modified", "name: new");
    expect(guidelinesDiff).toHaveAttribute("data-original", "Old guideline");
    expect(guidelinesDiff).toHaveAttribute("data-modified", "New guideline");
  });

  it("renders SME information above the champion diff", () => {
    render(<ScoreChampionVersionTimeline {...baseProps} />);

    expect(screen.getByText("SME Information")).toBeInTheDocument();
    const agenda = screen.getByText("Review boundary cases with the SME.");
    const worksheet = screen.getByText("Confirm the transfer criteria.");
    expect(agenda).toBeInTheDocument();
    expect(worksheet).toBeInTheDocument();
    expect(agenda).toHaveClass("text-foreground");
    expect(worksheet).toHaveClass("text-foreground");

    const content = document.body.textContent || "";
    expect(content.indexOf("SME Information")).toBeLessThan(content.indexOf("Champion Diff"));
  });

  it("loads compacted report output attachments", async () => {
    mockDownloadData.mockReturnValue({
      result: Promise.resolve({
        body: {
          text: () => Promise.resolve(JSON.stringify(output)),
        },
      }),
    });

    render(
      <ScoreChampionVersionTimeline
        {...baseProps}
        output={{
          output_compacted: true,
          output_attachment: "reportblocks/block-1/output-block-1.json",
        }}
      />
    );

    await waitFor(() => expect(screen.getByText("Scorecard: Scorecard A")).toBeInTheDocument());
    expect(screen.getByText("Score 1")).toBeInTheDocument();
    expect(screen.getByText("Score 2")).toBeInTheDocument();
    expect(mockDownloadData).toHaveBeenCalledWith({
      path: "reportblocks/block-1/output-block-1.json",
      options: { bucket: "reportBlockDetails" },
    });
  });
});
