import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import ScoreResultsReport from "@/components/blocks/ScoreResultsReport";

const mockDownloadData = jest.fn();

jest.mock("aws-amplify/storage", () => ({
  downloadData: (...args: any[]) => mockDownloadData(...args),
}));

jest.mock("@/components/blocks/ReportBlock", () => {
  const MockReportBlock = ({ title, subtitle, children }: any) => (
    <div>
      <div>{title}</div>
      {subtitle ? <div data-testid="report-subtitle">{subtitle}</div> : null}
      {children}
    </div>
  );
  return {
    __esModule: true,
    default: MockReportBlock,
  };
});

jest.mock("@/components/ui/score-result-trace", () => ({
  __esModule: true,
  ScoreResultTrace: ({ trace }: any) => (
    <div data-testid="structured-trace">{JSON.stringify(trace)}</div>
  ),
}));

describe("ScoreResultsReport", () => {
  beforeEach(() => {
    mockDownloadData.mockReset();
  });

  const output = {
    report_type: "score_results_report",
    block_title: "Score Results Report",
    scorecard_name: "Test Scorecard",
    summary: {
      input_identifier_count: 2,
      resolved_item_count: 2,
      total_predictions: 2,
      failed_predictions: 1,
    },
    unresolved_identifiers: [
      { input_identifier: "bad-id", error: "No item found" },
    ],
    failed_predictions: [
      { input_identifier: "311430190", score_name: "Score 1", error: "Prediction failed" },
    ],
    scores: [
      {
        score_id: "score-1",
        score_name: "Score 1",
        results: [
          {
            input_identifier: "311430191",
            resolved_item_id: "item-1",
            item_identifiers: [
              { name: "Customer ID", value: "CUST-311430191", url: "https://example.com/customer/CUST-311430191" },
              { name: "Conversation ID", value: "311430191" },
            ],
            status: "success",
            score_result_id: "sr-1",
            value: "yes",
            explanation: "Aligned behavior",
            cost: { total_cost: 0.2, prompt_tokens: 120, completion_tokens: 80 },
            trace: { node_results: [] },
          },
          {
            input_identifier: "311430190",
            resolved_item_id: "item-2",
            status: "failed",
            score_result_id: null,
            value: null,
            explanation: null,
            cost: null,
            trace: null,
            error: "Prediction failed",
          },
        ],
      },
    ],
  };

  const baseProps = {
    id: "block-1",
    config: {},
    output,
    log: undefined,
    name: "Score Results Report",
    position: 1,
    type: "ScoreResultsReport",
    attachedFiles: [],
  };

  it("renders grouped-by-score card rows, identifiers, value/explanation, and diagnostics", () => {
    render(<ScoreResultsReport {...baseProps} />);

    expect(screen.getByText("Score Results Report")).toBeInTheDocument();
    expect(screen.getByTestId("report-subtitle")).toHaveTextContent("Test Scorecard");
    expect(screen.queryByTestId("score-results-header-row")).not.toBeInTheDocument();
    expect(screen.getByTestId("score-section-score-1")).toBeInTheDocument();
    expect(screen.getByTestId("score-results-summary")).toHaveTextContent("Score Results: 2");
    expect(screen.getByTestId("score-results-summary")).toHaveTextContent("Input Tokens: 120");
    expect(screen.getByTestId("score-results-summary")).toHaveTextContent("Output Tokens: 80");
    expect(screen.getByTestId("score-results-summary")).toHaveTextContent("Total Cost: $0.20");
    expect(screen.queryByText("Scores: 1")).not.toBeInTheDocument();
    expect(screen.queryByText("Inputs:")).not.toBeInTheDocument();
    expect(screen.getByTestId("unresolved-identifiers")).toHaveTextContent("bad-id");
    expect(screen.queryByTestId("failed-predictions")).not.toBeInTheDocument();
    expect(screen.queryByText(/Requested Identifier:/)).not.toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === "Customer ID:")).toBeInTheDocument();
    expect(screen.getByText("Aligned behavior")).toBeInTheDocument();
    expect(screen.queryByText("Status success")).not.toBeInTheDocument();
    expect(screen.getByText("Status failed")).toBeInTheDocument();
    expect(screen.queryByText(/Result sr-1/)).not.toBeInTheDocument();
    expect(screen.getByText(/Cost \$0.20/)).toBeInTheDocument();
    expect(screen.getByText(/In 120 tok/)).toBeInTheDocument();
    expect(screen.getByText(/Out 80 tok/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("keeps traces collapsed by default and renders structured trace when expanded", () => {
    render(<ScoreResultsReport {...baseProps} />);

    expect(screen.queryByTestId("structured-trace")).not.toBeInTheDocument();
    const toggle = screen.getByTestId("trace-toggle-score-1-311430191-0");
    fireEvent.click(toggle);
    expect(screen.getByTestId("trace-content-score-1-311430191-0")).toBeInTheDocument();
    expect(screen.getByTestId("structured-trace")).toBeInTheDocument();
  });

  it("loads compacted output from attachment", async () => {
    mockDownloadData.mockReturnValue({
      result: Promise.resolve({
        body: {
          text: () => Promise.resolve(JSON.stringify(output)),
        },
      }),
    });

    render(
      <ScoreResultsReport
        {...baseProps}
        output={{
          output_compacted: true,
          output_attachment: "reportblocks/block-1/output-block-1.json",
        }}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("score-section-score-1")).toBeInTheDocument();
    });

    expect(mockDownloadData).toHaveBeenCalledWith({
      path: "reportblocks/block-1/output-block-1.json",
      options: { bucket: "reportBlockDetails" },
    });
  });

  it("shows loading state for compacted output before attachment resolves", async () => {
    let resolveBodyText: ((value: string) => void) | null = null;
    const textPromise = new Promise<string>((resolve) => {
      resolveBodyText = resolve;
    });

    mockDownloadData.mockReturnValue({
      result: Promise.resolve({
        body: {
          text: () => textPromise,
        },
      }),
    });

    render(
      <ScoreResultsReport
        {...baseProps}
        output={{
          output_compacted: true,
          output_attachment: "reportblocks/block-1/output-block-1.json",
        }}
      />
    );

    expect(screen.getByTestId("score-results-report-loading")).toBeInTheDocument();
    resolveBodyText?.(JSON.stringify(output));
    await waitFor(() => {
      expect(screen.queryByTestId("score-results-report-loading")).not.toBeInTheDocument();
    });
  });

  it("dedupes single-score title and keeps score name in the score section header", () => {
    render(
      <ScoreResultsReport
        {...baseProps}
        output={{
          ...output,
          block_title: "PolicyPoint - Non-Sales",
          scorecard_name: "Policy Point",
          score_name: "PolicyPoint - Non-Sales",
          scores: [{ score_id: "score-pp", score_name: "PolicyPoint - Non-Sales", results: [] }],
        }}
      />
    );

    expect(screen.getByText("Score Results Report")).toBeInTheDocument();
    expect(screen.getByTestId("report-subtitle")).toHaveTextContent("Policy Point");
    expect(screen.getAllByText("PolicyPoint - Non-Sales")).toHaveLength(1);
  });
});
