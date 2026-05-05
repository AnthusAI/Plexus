import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import ScorecardHistory from "@/components/blocks/ScorecardHistory";

const mockDownloadData = jest.fn();

jest.mock("aws-amplify/storage", () => ({
  downloadData: (...args: any[]) => mockDownloadData(...args),
}));

jest.mock("@monaco-editor/react", () => ({
  DiffEditor: ({ language, original, modified }: any) => (
    <div data-testid={`diff-editor-${language}`} data-original={original} data-modified={modified} />
  ),
}));

jest.mock("@/components/blocks/ReportBlock", () => {
  const MockReportBlock = ({ title, subtitle, subtitleClassName, children }: any) => (
    <div>
      <div>{title}</div>
      {subtitle ? <div data-testid="report-subtitle" className={subtitleClassName}>{subtitle}</div> : null}
      {children}
    </div>
  );
  return {
    __esModule: true,
    default: MockReportBlock,
  };
});

describe("ScorecardHistory", () => {
  beforeEach(() => {
    mockDownloadData.mockReset();
  });

  const output = {
    report_type: "scorecard_history",
    block_title: "Scorecard History",
    block_description: "Featured score-version changes and champion promotion status",
    scope: "scorecard_all_scores",
    scorecard_id: "scorecard-1",
    scorecard_name: "Select Quote HCS Medium Risk",
    date_range: {
      start: "2026-04-25T00:00:00+00:00",
      end: "2026-05-05T00:00:00+00:00",
    },
    summary: {
      text: "Overall history summary. Some included changes were promoted to champion.",
      champion_coverage: "some",
      featured_version_count: 1,
      champion_version_count: 1,
      scores_changed_count: 1,
    },
    scores: [
      {
        score_id: "score-1",
        score_name: "Agent Misrepresentation",
        summary: "The score tightened its routing criteria.",
        featured_version_count: 1,
        champion_version_count: 1,
        versions: [
          {
            version_id: "version-1",
            score_id: "score-1",
            note: "Tightened routing criteria for transfer cases.",
            branch: "optimizer",
            created_at: "2026-05-01T12:00:00+00:00",
            updated_at: "2026-05-01T12:00:00+00:00",
            parent_version_id: "version-0",
            champion_status: {
              is_current_champion: true,
              is_champion_related: true,
              promotions_in_window: [
                {
                  entered_at: "2026-05-02T12:00:00+00:00",
                  previous_champion_version_id: "version-0",
                  next_champion_version_id: null,
                },
              ],
            },
            diffs: {
              code: {
                original_version_id: "version-0",
                modified_version_id: "version-1",
                original_label: "Parent Code",
                modified_label: "Version Code",
                original: "name: old\n",
                modified: "name: new\n",
                unified_diff: "--- version-0/configuration\n+++ version-1/configuration\n-name: old\n+name: new",
                has_changes: true,
              },
              guidelines: {
                original_version_id: "version-0",
                modified_version_id: "version-1",
                original_label: "Parent Guidelines",
                modified_label: "Version Guidelines",
                original: "# Old\n",
                modified: "# New\n",
                unified_diff: "--- version-0/guidelines\n+++ version-1/guidelines\n-# Old\n+# New",
                has_changes: true,
              },
            },
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
    name: "Scorecard History",
    position: 1,
    type: "ScorecardHistory",
    attachedFiles: [],
  };

  it("shows top and score summaries while keeping versions and diffs collapsed by default", () => {
    render(<ScorecardHistory {...baseProps} />);

    expect(screen.getByText("Scorecard History")).toBeInTheDocument();
    expect(screen.getByTestId("report-subtitle")).toHaveTextContent("Select Quote HCS Medium Risk");
    expect(screen.getByTestId("scorecard-history-summary")).toHaveTextContent("Overall history summary");
    expect(screen.getByTestId("score-summary-score-1")).toHaveTextContent("tightened its routing criteria");
    expect(screen.queryByTestId("version-list-score-1")).not.toBeInTheDocument();
    expect(screen.queryByTestId("version-details-version-1")).not.toBeInTheDocument();
    expect(screen.queryByTestId("diff-editor-yaml")).not.toBeInTheDocument();
    expect(screen.queryByTestId("diff-editor-markdown")).not.toBeInTheDocument();
  });

  it("renders Monaco diffs only after expanding the score, version, and diff", () => {
    render(<ScorecardHistory {...baseProps} />);

    fireEvent.click(screen.getByRole("button", { name: /Score Versions/i }));
    expect(screen.getByTestId("version-list-score-1")).toBeInTheDocument();
    expect(screen.getByTestId("version-trigger-version-1")).toBeInTheDocument();
    expect(screen.queryByTestId("version-details-version-1")).not.toBeInTheDocument();
    expect(screen.queryByTestId("diff-editor-yaml")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("version-trigger-version-1"));
    expect(screen.getByTestId("version-details-version-1")).toBeInTheDocument();
    expect(screen.getByText("Version Note")).toBeInTheDocument();
    expect(screen.queryByTestId("diff-editor-yaml")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Code Diff/i }));
    expect(screen.getByTestId("code-diff-version-1")).toBeInTheDocument();
    expect(screen.getByTestId("diff-editor-yaml")).toHaveAttribute("data-original", "name: old\n");
    expect(screen.getByTestId("diff-editor-yaml")).toHaveAttribute("data-modified", "name: new\n");
  });

  it("loads compacted output from the report block details attachment", async () => {
    mockDownloadData.mockReturnValue({
      result: Promise.resolve({
        body: {
          text: () => Promise.resolve(JSON.stringify(output)),
        },
      }),
    });

    render(
      <ScorecardHistory
        {...baseProps}
        output={{
          output_compacted: true,
          output_attachment: "reportblocks/block-1/output-block-1.json",
        }}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("scorecard-history-summary")).toHaveTextContent("Overall history summary");
    });
    expect(mockDownloadData).toHaveBeenCalledWith({
      path: "reportblocks/block-1/output-block-1.json",
      options: { bucket: "reportBlockDetails" },
    });
  });
});
