import * as React from "react"
import { render, screen, waitFor } from "@testing-library/react"
import { useAuthenticator } from "@aws-amplify/ui-react"
import { generateClient } from "aws-amplify/api"
import { listFromModel } from "@/utils/amplify-helpers"
import DashboardLayout from "@/components/dashboard-layout"
import { SidebarProvider } from "@/app/contexts/SidebarContext"
import { ThemeProvider } from "next-themes"
import type { Schema } from "@/amplify/data/resource"
import { AccountProvider } from "@/app/contexts/AccountContext"

jest.mock("@aws-amplify/ui-react", () => ({
  useAuthenticator: jest.fn()
}))

jest.mock("aws-amplify/api")
jest.mock("@/utils/amplify-helpers")

const mockListFromModel = listFromModel as jest.MockedFunction<typeof listFromModel>
const mockUseAuthenticator = useAuthenticator as jest.MockedFunction<typeof useAuthenticator>
const mockGenerateClient = generateClient as unknown as jest.Mock

type Account = Schema["Account"]["type"]

describe("DashboardLayout", () => {
  const mockSignOut = jest.fn()
  const mockClient = {
    models: {
      Account: {
        list: jest.fn().mockResolvedValue({ data: [] })
      }
    }
  }

  beforeEach(() => {
    mockUseAuthenticator.mockReturnValue({ authStatus: "authenticated" } as any)
    mockListFromModel.mockResolvedValue({ 
      data: [{
        id: "1",
        name: "Test Account",
        key: "test",
        settings: null,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      } as Account], 
      nextToken: null 
    })
    mockGenerateClient.mockReturnValue(mockClient)
    ;(global as any).client = mockClient
  })

  afterEach(() => {
    jest.clearAllMocks()
  })

  const renderDashboardLayout = () => {
    return render(
      <ThemeProvider attribute="class">
        <AccountProvider>
          <SidebarProvider>
            <DashboardLayout signOut={mockSignOut}>
              <div>Test Content</div>
            </DashboardLayout>
          </SidebarProvider>
        </AccountProvider>
      </ThemeProvider>
    )
  }

  it("shows all menu items when account has no settings", async () => {
    mockListFromModel.mockResolvedValue({
      data: [{
        id: "1",
        name: "Test Account",
        key: "test",
        settings: null,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      } as Account],
      nextToken: null
    })

    renderDashboardLayout()

    await waitFor(() => {
      expect(screen.getByText("Feedback")).toBeInTheDocument()
      expect(screen.getByText("Activity")).toBeInTheDocument()
      expect(screen.getByText("Scorecards")).toBeInTheDocument()
    })
  })

  it("hides menu items specified in account settings", async () => {
    mockListFromModel.mockResolvedValue({
      data: [{
        id: "1",
        name: "Test Account",
        key: "test",
        settings: JSON.stringify({
          hiddenMenuItems: ["Feedback", "Activity"]
        }),
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      } as Account],
      nextToken: null
    })

    renderDashboardLayout()

    await waitFor(() => {
      expect(screen.queryByText("Feedback")).not.toBeInTheDocument()
      expect(screen.queryByText("Activity")).not.toBeInTheDocument()
      expect(screen.getByText("Scorecards")).toBeInTheDocument()
    })
  })

  it("shows all menu items when settings are invalid", async () => {
    mockListFromModel.mockResolvedValue({
      data: [{
        id: "1",
        name: "Test Account",
        key: "test",
        settings: JSON.stringify({
          hiddenMenuItems: "not an array"
        }),
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      } as Account],
      nextToken: null
    })

    renderDashboardLayout()

    await waitFor(() => {
      expect(screen.getByText("Feedback")).toBeInTheDocument()
      expect(screen.getByText("Activity")).toBeInTheDocument()
      expect(screen.getByText("Scorecards")).toBeInTheDocument()
    })
  })

  it("handles string settings being already parsed", async () => {
    mockListFromModel.mockResolvedValue({
      data: [{
        id: "1",
        name: "Test Account",
        key: "test",
        settings: {
          hiddenMenuItems: ["Feedback"]
        },
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      } as Account],
      nextToken: null
    })

    renderDashboardLayout()

    await waitFor(() => {
      expect(screen.queryByText("Feedback")).not.toBeInTheDocument()
      expect(screen.getByText("Activity")).toBeInTheDocument()
      expect(screen.getByText("Scorecards")).toBeInTheDocument()
    })
  })
}) 