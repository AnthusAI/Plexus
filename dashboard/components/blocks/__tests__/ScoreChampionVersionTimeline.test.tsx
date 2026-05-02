import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

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
  TabsTrigger: ({ children, ...props }: any) => <button {...props}>{children}</button>,
}));

jest.mock("recharts", () => ({
  CartesianGrid: () => null,
  Customized: ({ component }: any) =>
    React.isValidElement(component)
      ? React.cloneElement(component, {
          xAxisMap: { 0: { scale: (value: number) => value / 1000000000 } },
          offset: { top: 0, height: 100 },
        } as any)
      : null,
  Line: ({ dataKey, yAxisId, strokeDasharray }: any) => (
    <g data-testid={`line-${dataKey}`} data-y-axis-id={yAxisId} data-stroke-dasharray={strokeDasharray || ""} />
  ),
  LineChart: ({ children }: any) => <svg data-testid="line-chart">{children}</svg>,
  Tooltip: () => null,
  XAxis: ({ domain }: any) => <g data-testid="x-axis" data-domain={Array.isArray(domain) ? domain.join(",") : ""} />,
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
    scorecard_id: "scorecard-1",
    scorecard_name: "Scorecard A",
    date_range: {
      start: "2026-04-01T00:00:00+00:00",
      end: "2026-04-30T23:59:59+00:00",
    },
    summary: {
      scores_analyzed: 2,
      scores_with_champion_changes: 2,
      scores_with_new_champions: 0,
      champion_change_count: 2,
      new_champion_count: 0,
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
          agenda: "## SME Agenda\n\n- Review boundary cases with the SME.",
          worksheet: "### Worksheet\n\nConfirm the transfer criteria.",
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
        champion_change_count: 1,
        new_champion_count: 0,
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
        champion_change_count: 1,
        new_champion_count: 0,
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
    expect(screen.queryByText("Evaluation Record Cost")).not.toBeInTheDocument();
    expect(screen.queryByText(/Eval records:/)).not.toBeInTheDocument();
    expect(screen.getAllByTestId("chart-container")).toHaveLength(2);
    expect(screen.queryByTestId("line-timeline_marker")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("champion-transition-marker-layer")).toHaveLength(2);
    expect(screen.getAllByTestId("champion-transition-marker")).toHaveLength(2);
    expect(screen.getAllByTestId("champion-transition-marker")[0]).toHaveAttribute("width", "20");
    expect(screen.getAllByTestId("champion-transition-marker")[0]).toHaveAttribute("height", "8");
    expect(screen.getAllByTestId("champion-transition-marker")[0]).toHaveAttribute("y", "103");
    expect(screen.getByTestId("line-feedback_alignment")).toHaveAttribute("data-y-axis-id", "alignment");
    expect(screen.getByTestId("line-feedback_accuracy")).toHaveAttribute("data-y-axis-id", "accuracy");
    expect(screen.getByTestId("line-feedback_accuracy")).toHaveAttribute("data-stroke-dasharray", "5 5");
    expect(screen.queryByTestId("line-regression_alignment")).not.toBeInTheDocument();
    expect(screen.queryByTestId("line-regression_accuracy")).not.toBeInTheDocument();
    expect(screen.queryByText("Select score")).not.toBeInTheDocument();
  });

  it("keeps version tables sized to their row content", () => {
    render(<ScoreChampionVersionTimeline {...baseProps} />);

    for (const table of screen.getAllByTestId(/^version-table-/)) {
      expect(table.className).toContain("h-auto");
      expect(table.className).toContain("max-h-none");
      expect(table.className).toContain("overflow-y-visible");
      expect(table.className).not.toMatch(/h-\[/);
      expect(table.className).not.toMatch(/max-h-\[/);
    }
  });

  it("links score and score-version short ids to their detail routes", () => {
    const { container } = render(<ScoreChampionVersionTimeline {...baseProps} />);

    expect(
      container.querySelector('a[href="/lab/scorecards/scorecard-1/scores/score-1"][aria-label="Open score"]')
    ).toBeInTheDocument();
    expect(
      container.querySelector(
        'a[href="/lab/scorecards/scorecard-1/scores/score-1/versions/version-1"][aria-label="Open score version"]'
      )
    ).toBeInTheDocument();
    expect(
      container.querySelector(
        'a[href="/lab/scorecards/scorecard-1/scores/score-1/versions/version-0"][aria-label="Open previous champion score version"]'
      )
    ).toBeInTheDocument();
    expect(
      container.querySelector(
        'a[href="/lab/scorecards/scorecard-1/scores/score-1/versions/version-1"][aria-label="Open latest champion score version"]'
      )
    ).toBeInTheDocument();
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

  it("lazily renders diff editors only after a diff is opened", () => {
    render(<ScoreChampionVersionTimeline {...baseProps} />);

    expect(screen.getAllByText("Champion Diff")).toHaveLength(2);
    expect(screen.getAllByText("Show diff")).toHaveLength(2);
    expect(screen.queryByTestId("diff-editor-yaml")).not.toBeInTheDocument();
    expect(screen.queryByTestId("diff-editor-markdown")).not.toBeInTheDocument();

    fireEvent.click(screen.getAllByText("Show diff")[0]);

    expect(screen.getByText("Hide diff")).toBeInTheDocument();
    expect(screen.getByText("Code")).toBeInTheDocument();
    expect(screen.getByText("Guidelines")).toBeInTheDocument();
    const codeDiff = screen.getByTestId("diff-editor-yaml");
    expect(codeDiff).toHaveAttribute("data-original", "name: old");
    expect(codeDiff).toHaveAttribute("data-modified", "name: new");
    expect(screen.queryByTestId("diff-editor-markdown")).not.toBeInTheDocument();
  });

  it("renders champion diff above SME information", () => {
    render(<ScoreChampionVersionTimeline {...baseProps} />);

    expect(screen.getByText("SME Information")).toBeInTheDocument();
    expect(screen.getAllByText("Show more")).toHaveLength(2);
    const agenda = screen.getByTestId("sme-agenda-markdown");
    const worksheet = screen.getByTestId("sme-worksheet-markdown");
    expect(agenda.tagName).toBe("DIV");
    expect(worksheet.tagName).toBe("DIV");
    expect(agenda).toHaveTextContent("SME Agenda");
    expect(agenda).toHaveTextContent("Review boundary cases with the SME.");
    expect(worksheet).toHaveTextContent("Worksheet");
    expect(worksheet).toHaveTextContent("Confirm the transfer criteria.");
    expect(agenda).toHaveClass("text-foreground");
    expect(worksheet).toHaveClass("text-foreground");
    expect(agenda.className).not.toContain("overflow-auto");
    expect(agenda.className).not.toContain("max-h-");
    expect(worksheet.className).not.toContain("overflow-auto");
    expect(worksheet.className).not.toContain("max-h-");

    const content = document.body.textContent || "";
    expect(content.indexOf("Champion Diff")).toBeLessThan(content.indexOf("SME Information"));
  });

  it("keeps SME markdown collapsed until expanded", () => {
    render(<ScoreChampionVersionTimeline {...baseProps} />);

    const agenda = screen.getByTestId("sme-agenda-markdown");
    const collapsedWrapper = agenda.parentElement;
    expect(collapsedWrapper?.className).toContain("max-h-24");
    expect(collapsedWrapper?.className).toContain("overflow-hidden");

    fireEvent.click(screen.getAllByText("Show more")[0]);

    expect(screen.getByText("Show less")).toBeInTheDocument();
    expect(agenda.parentElement?.className).not.toContain("max-h-24");
    expect(agenda.parentElement?.className).not.toContain("overflow-hidden");
  });

  it("does not render SME information when there is no SME agenda", () => {
    render(
      <ScoreChampionVersionTimeline
        {...baseProps}
        output={{
          ...output,
          scores: [
            {
              ...output.scores[0],
              sme: {
                procedure_id: "procedure-1",
                procedure_status: "COMPLETED",
                available: false,
                agenda: null,
                worksheet: "Worksheet without agenda should not render.",
              },
            },
          ],
        }}
      />
    );

    expect(screen.queryByText("SME Information")).not.toBeInTheDocument();
    expect(screen.queryByTestId("sme-agenda-markdown")).not.toBeInTheDocument();
    expect(screen.queryByText("Worksheet without agenda should not render.")).not.toBeInTheDocument();
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
