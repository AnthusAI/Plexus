import React from "react"
import { render, screen } from "@testing-library/react"

import ReportTask from "@/components/ReportTask"

jest.mock("@/utils/amplify-client", () => ({
  getClient: jest.fn(() => ({
    graphql: jest.fn().mockResolvedValue({
      data: {
        getReport: {
          reportBlocks: { items: [] },
        },
      },
    }),
  })),
}))

jest.mock("@/components/ui/task-author-indicator", () => ({
  TaskAuthorIndicator: ({ createdByUserId }: { createdByUserId?: string | null }) =>
    createdByUserId ? <div data-testid="task-author-indicator-mock">{createdByUserId}</div> : null,
}))

const baseTask = {
  id: "report-1",
  type: "Report",
  name: "",
  description: "",
  scorecard: "",
  score: "",
  time: "2026-01-01T00:00:00.000Z",
  data: {
    id: "report-1",
    title: "Report",
    name: "Report",
    configName: "Report",
    configDescription: "desc",
    createdByUserId: "user-1",
  },
}

describe("ReportTask author placement", () => {
  it("renders author slot in grid and detail variants", () => {
    const { rerender } = render(<ReportTask variant="grid" task={baseTask as any} />)

    expect(screen.getByTestId("report-task-author-grid-slot")).toBeInTheDocument()
    expect(screen.getByText("user-1")).toBeInTheDocument()

    rerender(<ReportTask variant="detail" task={baseTask as any} />)

    expect(screen.getByTestId("report-task-author-detail-slot")).toBeInTheDocument()
    expect(screen.getByText("user-1")).toBeInTheDocument()
  })

  it("keeps slot wrappers but no indicator when author is missing", () => {
    const taskWithoutAuthor = {
      ...baseTask,
      data: { ...baseTask.data, createdByUserId: null },
    }
    render(<ReportTask variant="grid" task={taskWithoutAuthor as any} />)

    expect(screen.getByTestId("report-task-author-grid-slot")).toBeInTheDocument()
    expect(screen.queryByTestId("task-author-indicator-mock")).not.toBeInTheDocument()
  })
})
