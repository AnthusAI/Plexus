import React from "react"
import { render, screen } from "@testing-library/react"

import { ScoreSidebarVersionHistory } from "@/components/ui/score-sidebar-version-history"

jest.mock("@/components/ui/task-author-indicator", () => ({
  TaskAuthorIndicator: ({ createdByUserId }: { createdByUserId?: string | null }) =>
    createdByUserId ? <div data-testid="task-author-indicator-mock">{createdByUserId}</div> : null,
}))

describe("ScoreSidebarVersionHistory author indicator", () => {
  it("renders author indicator when version has createdByUserId", () => {
    render(
      <ScoreSidebarVersionHistory
        versions={[
          {
            id: "v1",
            scoreId: "score-1",
            configuration: "key: value",
            createdAt: "2026-01-01T00:00:00.000Z",
            updatedAt: "2026-01-01T00:00:00.000Z",
            createdByUserId: "user-1",
          },
        ]}
      />
    )

    expect(screen.getByTestId("task-author-indicator-mock")).toHaveTextContent("user-1")
  })

  it("hides author indicator when createdByUserId is missing", () => {
    render(
      <ScoreSidebarVersionHistory
        versions={[
          {
            id: "v1",
            scoreId: "score-1",
            configuration: "key: value",
            createdAt: "2026-01-01T00:00:00.000Z",
            updatedAt: "2026-01-01T00:00:00.000Z",
          },
        ]}
      />
    )

    expect(screen.queryByTestId("task-author-indicator-mock")).not.toBeInTheDocument()
  })
})
