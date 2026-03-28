import * as React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"

import ConsoleDashboard from "../console-dashboard"
import { CONSOLE_BUILTIN_PROCEDURE_ID } from "@/components/console/constants"

const mockPush = jest.fn()
const mockUseAccount = jest.fn(() => ({
  selectedAccount: { id: "acct-1", name: "Test Account" },
}))

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}))

jest.mock("@/app/contexts/AccountContext", () => ({
  useAccount: () => mockUseAccount(),
}))

jest.mock("@/components/ScorecardContext", () => ({
  __esModule: true,
  default: () => <div data-testid="scorecard-context">scorecard context</div>,
}))

jest.mock("@/components/console/console-chat-elements-adapter", () => ({
  __esModule: true,
  default: ({
    procedureId,
    accountId,
    selectedSessionId,
    onSessionSelect,
  }: {
    procedureId: string
    accountId: string
    selectedSessionId?: string
    onSessionSelect?: (sessionId: string) => void
  }) => (
    <div>
      <div data-testid="console-chat-adapter">
        {procedureId}:{accountId}:{selectedSessionId || "none"}
      </div>
      <button onClick={() => onSessionSelect?.("session-picked")}>Select Session</button>
    </div>
  ),
}))

jest.mock("@/components/activity-dashboard", () => ({
  __esModule: true,
  default: ({ embedded, showHeader }: { embedded?: boolean; showHeader?: boolean }) => (
    <div data-testid="activity-dashboard">
      {embedded ? "embedded" : "standalone"}-{showHeader ? "header" : "no-header"}
    </div>
  ),
}))

jest.mock("@/components/task-dispatch", () => ({
  TaskDispatchButton: ({ config }: { config: { actions: Array<any> } }) => (
    <div>
      {config.actions.map((action) => (
        <button
          key={action.name}
          onClick={() => {
            if (action.actionType === "ui") {
              action.onSelect()
            }
          }}
        >
          {action.name}
        </button>
      ))}
    </div>
  ),
  activityConfig: {
    buttonLabel: "Actions",
    actions: [],
    dialogs: {},
  },
}))

describe("ConsoleDashboard", () => {
  beforeEach(() => {
    mockPush.mockReset()
    mockUseAccount.mockReturnValue({
      selectedAccount: { id: "acct-1", name: "Test Account" },
    })
  })

  it("renders top controls and chat workspace with artifact pane collapsed by default", async () => {
    render(<ConsoleDashboard />)

    expect(screen.getByTestId("scorecard-context")).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByTestId("console-chat-adapter")).toHaveTextContent(
        `${CONSOLE_BUILTIN_PROCEDURE_ID}:acct-1:none`
      )
    })
    expect(screen.queryByTestId("activity-dashboard")).not.toBeInTheDocument()
  })

  it("binds route session id and updates URL when selecting a session", async () => {
    render(<ConsoleDashboard routeSessionId="session-in-url" />)

    await waitFor(() => {
      expect(screen.getByTestId("console-chat-adapter")).toHaveTextContent(
        `${CONSOLE_BUILTIN_PROCEDURE_ID}:acct-1:session-in-url`
      )
    })

    fireEvent.click(screen.getByText("Select Session"))
    expect(mockPush).toHaveBeenCalledWith("/lab/console/session-picked")
  })

  it("opens the activity artifact pane from the Show Activity action", async () => {
    render(<ConsoleDashboard />)

    await waitFor(() => {
      expect(screen.getByTestId("console-chat-adapter")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText("Show Activity"))

    expect(screen.getByTestId("activity-dashboard")).toHaveTextContent("embedded-no-header")
  })

  it("shows unavailable state when account context is missing", async () => {
    mockUseAccount.mockReturnValue({
      selectedAccount: null,
    })

    render(<ConsoleDashboard />)

    await waitFor(() => {
      expect(screen.getByText("Console unavailable")).toBeInTheDocument()
    })
    expect(screen.getByText(/select an account/i)).toBeInTheDocument()
    expect(screen.queryByTestId("console-chat-adapter")).not.toBeInTheDocument()
  })
})
