import React from "react"
import { fireEvent, render, screen } from "@testing-library/react"

import OptimizationOpportunityDistribution, {
  type OptimizationOpportunityRow,
} from "@/components/OptimizationOpportunityDistribution"

jest.mock("@/components/ui/chart", () => ({
  ChartContainer: ({ children }: any) => <div data-testid="chart-container">{children}</div>,
}))

jest.mock("recharts", () => ({
  CartesianGrid: () => null,
  ComposedChart: ({ children }: any) => <div data-testid="opportunity-composed-chart">{children}</div>,
  Legend: () => null,
  Line: ({ dataKey }: any) => <div data-testid="opportunity-line" data-key={dataKey} />,
  Scatter: ({ data, fill, name }: any) => (
    <div
      data-testid={`disposition-${name}`}
      data-fill={fill}
      data-point-count={data.length}
      data-marker-radius={data[0]?.marker_radius}
      data-disagreement-fraction={data[0]?.disagreement_fraction}
    />
  ),
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: ({ scale }: any) => <div data-testid="opportunity-y-axis" data-scale={scale} />,
}))

describe("OptimizationOpportunityDistribution", () => {
  const rows: OptimizationOpportunityRow[] = [
    {
      evidence_rank: 2,
      opportunity: 8,
      disposition: "cooldown",
      scorecard_name: "North portfolio",
      score_name: "Follow-up timing",
      eligibility_timestamp: "2026-08-01T00:00:00Z",
    },
    {
      evidence_rank: 1,
      opportunity: 24,
      disposition: "selected_for_review",
      scorecard_name: "North portfolio",
      score_name: "Opening confirmation",
      reason: "Highest reviewed-error opportunity",
      dashboard_url: "/lab/scorecards/example/scores/opening-confirmation",
    },
    {
      evidence_rank: 3,
      opportunity: 0,
      disposition: "incomplete",
      scorecard_name: "South portfolio",
      score_name: "Closing summary",
      reason: "Evidence is incomplete",
    },
    {
      evidence_rank: 4,
      opportunity: 3,
      disposition: "eligible",
      scorecard_name: "South portfolio",
      score_name: "Availability check",
    },
    {
      evidence_rank: 5,
      opportunity: 1,
      disposition: "blocked",
      scorecard_name: "West portfolio",
      score_name: "Policy statement",
    },
  ]

  it("renders the complete ranked curve, stakeholder-safe legend, and text equivalent", () => {
    render(<OptimizationOpportunityDistribution rows={rows} />)

    expect(screen.getByText("Opportunity distribution")).toBeInTheDocument()
    expect(screen.getByTestId("opportunity-composed-chart")).toBeInTheDocument()
    expect(screen.getByTestId("opportunity-line")).toHaveAttribute("data-key", "chart_opportunity")
    expect(screen.getByText("Selected for review (1)")).toBeInTheDocument()
    expect(screen.getByText("Cooling down (1)")).toBeInTheDocument()
    expect(screen.getByText("Incomplete evidence (1)")).toBeInTheDocument()
    expect(screen.getByText("North portfolio — Opening confirmation")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "North portfolio — Opening confirmation" })).toHaveAttribute(
      "href",
      "/lab/scorecards/example/scores/opening-confirmation",
    )
    expect(screen.queryByText(/opaque-/i)).not.toBeInTheDocument()

    fireEvent.click(screen.getByText("Text equivalent: evidence-ranked opportunity list"))
    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(screen.getByText("Highest reviewed-error opportunity")).toBeInTheDocument()
  })

  it("switches between linear and logarithmic views and explains zero-value placement", () => {
    render(<OptimizationOpportunityDistribution rows={rows} />)

    expect(screen.getByTestId("opportunity-y-axis")).toHaveAttribute("data-scale", "linear")
    fireEvent.click(screen.getByRole("button", { name: "Log" }))

    expect(screen.getByTestId("opportunity-y-axis")).toHaveAttribute("data-scale", "log")
    expect(screen.getByText(/Zero-valued opportunities are placed at the chart floor/i)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Log" })).toHaveAttribute("aria-pressed", "true")
  })

  it("shows disagreement rate and valid feedback volume as visual signals with a text equivalent", () => {
    const rowsWithFeedbackSignals = rows.map((row, index) => ({
      ...row,
      disagreement_rate: [0.42, 0.18, 0.07, 0.31, 0.12][index],
      valid_feedback_count: [240, 120, 35, 84, 60][index],
    }))

    render(<OptimizationOpportunityDistribution rows={rowsWithFeedbackSignals} />)

    expect(screen.getByText(/Point size represents valid feedback volume/i)).toBeInTheDocument()
    expect(screen.getByText(/Inner fill represents disagreement rate/i)).toBeInTheDocument()
    expect(screen.getByLabelText("Feedback visual encoding key")).toBeInTheDocument()
    expect(screen.getByText("Less feedback")).toBeInTheDocument()
    expect(screen.getByText("More feedback")).toBeInTheDocument()
    expect(screen.getByText("Lower disagreement")).toBeInTheDocument()
    expect(screen.getByText("Higher disagreement")).toBeInTheDocument()
    expect(screen.getByTestId("disposition-Selected for review")).toHaveAttribute("data-fill", "var(--chart-1)")
    expect(screen.getByTestId("disposition-Cooling down")).toHaveAttribute("data-marker-radius", "10")
    expect(screen.getByTestId("disposition-Selected for review")).toHaveAttribute("data-disagreement-fraction", "0.18")

    fireEvent.click(screen.getByText("Text equivalent: evidence-ranked opportunity list"))
    expect(screen.getByRole("columnheader", { name: "Disagreement" })).toBeInTheDocument()
    expect(screen.getByRole("columnheader", { name: "Valid feedback" })).toBeInTheDocument()
    expect(screen.getByText("42%")).toBeInTheDocument()
    expect(screen.getByText("240")).toBeInTheDocument()
  })

  it("does not render without opportunity rows", () => {
    const { container } = render(<OptimizationOpportunityDistribution rows={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
