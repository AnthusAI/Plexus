"use client"

import * as React from "react"
import { Activity, PanelRightClose, PanelRightOpen, Play, KanbanSquare, FileBarChart } from "lucide-react"
import { toast } from "sonner"
import { useRouter } from "next/navigation"

import { useAccount } from "@/app/contexts/AccountContext"
import ActivityDashboard from "@/components/activity-dashboard"
import ConsoleChatElementsAdapter from "@/components/console/console-chat-elements-adapter"
import { CONSOLE_BUILTIN_PROCEDURE_ID } from "@/components/console/constants"
import type { ConsoleArtifactKind } from "@/components/console/types"
import { useConsoleArtifact } from "@/components/console/use-console-artifact"
import ScorecardContext from "@/components/ScorecardContext"
import { activityConfig, TaskDispatchButton, type TaskDispatchConfig, type TaskUiAction } from "@/components/task-dispatch"
import { Button } from "@/components/ui/button"
import { createTask, getClient } from "@/utils/data-operations"

const LIST_ACCOUNT_BY_KEY_QUERY = `
  query ListConsoleAccountByKey($key: String!, $limit: Int) {
    listAccountByKey(key: $key, limit: $limit) {
      items {
        id
      }
    }
  }
`

function ArtifactPlaceholder({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="max-w-sm text-center text-muted-foreground">
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-muted/50">
          {icon}
        </div>
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="mt-1 text-xs">{description}</p>
      </div>
    </div>
  )
}

interface ConsoleDashboardProps {
  routeSessionId?: string
}

export default function ConsoleDashboard({ routeSessionId }: ConsoleDashboardProps) {
  const router = useRouter()
  const { selectedAccount } = useAccount()
  const [selectedScorecard, setSelectedScorecard] = React.useState<string | null>(null)
  const [selectedScore, setSelectedScore] = React.useState<string | null>(null)
  const { artifact, openArtifact, collapseArtifact, setArtifactWidth, expandLastArtifact } = useConsoleArtifact()
  const workspaceRef = React.useRef<HTMLDivElement | null>(null)
  const artifactPaneRef = React.useRef<HTMLElement | null>(null)
  const [workspaceWidth, setWorkspaceWidth] = React.useState(0)
  const [fallbackAccountId, setFallbackAccountId] = React.useState<string | null>(null)
  const selectedProcedureId = CONSOLE_BUILTIN_PROCEDURE_ID
  const selectedAccountId = selectedAccount?.id?.trim() || null
  const defaultAccountKey = process.env.NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY?.trim() || ""
  const effectiveAccountId = selectedAccountId || fallbackAccountId
  const normalizedRouteSessionId = routeSessionId?.trim() || undefined
  const [selectedSessionId, setSelectedSessionId] = React.useState<string | undefined>(normalizedRouteSessionId)

  React.useEffect(() => {
    setSelectedSessionId(normalizedRouteSessionId)
  }, [normalizedRouteSessionId])

  const getSessionIdFromPathname = React.useCallback((pathname: string): string | undefined => {
    if (!pathname.startsWith('/lab/console')) {
      return undefined
    }
    const suffix = pathname.slice('/lab/console'.length)
    if (!suffix || suffix === '/') {
      return undefined
    }
    const encoded = suffix.startsWith('/') ? suffix.slice(1) : suffix
    if (!encoded) {
      return undefined
    }
    try {
      return decodeURIComponent(encoded)
    } catch {
      return encoded
    }
  }, [])

  React.useEffect(() => {
    const handlePopState = () => {
      setSelectedSessionId(getSessionIdFromPathname(window.location.pathname))
    }

    window.addEventListener('popstate', handlePopState)
    return () => {
      window.removeEventListener('popstate', handlePopState)
    }
  }, [getSessionIdFromPathname])

  React.useEffect(() => {
    if (selectedAccountId) {
      setFallbackAccountId(null)
      return
    }
    if (!defaultAccountKey) {
      return
    }

    let cancelled = false

    const loadFallbackAccountId = async () => {
      try {
        const client = getClient() as any
        const response = await client.graphql({
          query: LIST_ACCOUNT_BY_KEY_QUERY,
          variables: { key: defaultAccountKey, limit: 1 },
          authMode: 'apiKey',
        })
        const id = response?.data?.listAccountByKey?.items?.[0]?.id
        if (!cancelled && typeof id === 'string' && id.trim()) {
          setFallbackAccountId(id.trim())
        }
      } catch (error) {
        console.error('[ConsoleDashboard] failed to resolve fallback account id', {
          defaultAccountKey,
          error,
        })
      }
    }

    void loadFallbackAccountId()

    return () => {
      cancelled = true
    }
  }, [defaultAccountKey, selectedAccountId])

  const handleSelectSession = React.useCallback((sessionId: string) => {
    const normalizedSessionId = sessionId.trim()
    if (!normalizedSessionId) {
      return
    }
    if (selectedSessionId === normalizedSessionId) {
      return
    }
    setSelectedSessionId(normalizedSessionId)
    const nextPath = `/lab/console/${encodeURIComponent(normalizedSessionId)}`
    if (window.location.pathname !== nextPath) {
      router.replace(nextPath)
    }
  }, [selectedSessionId, router])

  const handleShowActivity = React.useCallback(() => {
    openArtifact('activity', { title: "Activity" })
  }, [openArtifact])
  const handleShowBoard = React.useCallback(() => {
    openArtifact('board', { title: "Board" })
  }, [openArtifact])
  const handleShowReport = React.useCallback(() => {
    openArtifact('report', { title: "Report" })
  }, [openArtifact])

  const handleRunConsoleRepl = React.useCallback(async () => {
    if (!effectiveAccountId) {
      toast.error("Console account context is unavailable")
      return
    }

    try {
      const task = await createTask({
        type: "Procedure Run",
        target: `procedure/run/${selectedProcedureId}`,
        command: `procedure run ${selectedProcedureId}`,
        accountId: effectiveAccountId,
        dispatchStatus: "PENDING",
        status: "PENDING",
      })
      if (task) {
        toast.success("Console REPL run queued")
      } else {
        toast.error("Failed to queue console REPL run")
      }
    } catch (error) {
      console.error("Error queueing console REPL run:", error)
      toast.error("Error queueing console REPL run")
    }
  }, [effectiveAccountId, selectedProcedureId])

  const actionsConfig = React.useMemo<TaskDispatchConfig>(() => {
    const showActivityAction: TaskUiAction = {
      actionType: "ui",
      name: "Show Activity",
      icon: <PanelRightOpen className="mr-2 h-4 w-4" />,
      onSelect: handleShowActivity,
      description: "Open the activity artifact pane",
    }

    const runReplAction: TaskUiAction = {
      actionType: "ui",
      name: "Run Console REPL",
      icon: <Play className="mr-2 h-4 w-4" />,
      onSelect: handleRunConsoleRepl,
      description: "Queue one REPL cycle for the built-in Console procedure",
    }

    const showBoardAction: TaskUiAction = {
      actionType: "ui",
      name: "Show Board",
      icon: <KanbanSquare className="mr-2 h-4 w-4" />,
      onSelect: handleShowBoard,
      description: "Open the board artifact pane",
    }

    const showReportAction: TaskUiAction = {
      actionType: "ui",
      name: "Show Report",
      icon: <FileBarChart className="mr-2 h-4 w-4" />,
      onSelect: handleShowReport,
      description: "Open a report artifact pane",
    }

    return {
      buttonLabel: activityConfig.buttonLabel,
      actions: [showActivityAction, showBoardAction, showReportAction, runReplAction, ...activityConfig.actions],
      dialogs: activityConfig.dialogs,
    }
  }, [handleRunConsoleRepl, handleShowActivity, handleShowBoard, handleShowReport])

  React.useEffect(() => {
    const node = workspaceRef.current
    if (!node) return

    const updateWidth = () => {
      setWorkspaceWidth(node.getBoundingClientRect().width)
    }

    updateWidth()
    const observer = new ResizeObserver(updateWidth)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  const maxArtifactWidth = React.useMemo(() => {
    if (!workspaceWidth) return 900
    const minConversationPaneWidth = 520
    return Math.max(320, Math.min(900, Math.floor(workspaceWidth - minConversationPaneWidth)))
  }, [workspaceWidth])

  const artifactPaneWidth = React.useMemo(
    () => Math.max(320, Math.min(artifact.width, maxArtifactWidth)),
    [artifact.width, maxArtifactWidth]
  )

  React.useEffect(() => {
    if (artifact.width > maxArtifactWidth) {
      setArtifactWidth(maxArtifactWidth)
    }
  }, [artifact.width, maxArtifactWidth, setArtifactWidth])

  const artifactTitle = React.useMemo(() => {
    if (artifact.payload?.title) {
      return artifact.payload.title
    }
    const titles: Record<Exclude<ConsoleArtifactKind, 'none'>, string> = {
      activity: "Activity",
      board: "Board",
      report: "Report",
    }
    return artifact.kind === 'none' ? "Artifact" : titles[artifact.kind]
  }, [artifact.kind, artifact.payload?.title])

  const startArtifactResize = React.useCallback((event: React.MouseEvent) => {
    event.preventDefault()
    const workspaceRect = workspaceRef.current?.getBoundingClientRect()
    if (!workspaceRect) {
      return
    }
    const currentArtifactWidth = artifactPaneRef.current?.getBoundingClientRect().width ?? artifactPaneWidth
    const pointerOffset = workspaceRect.right - event.clientX - currentArtifactWidth

    const onMouseMove = (moveEvent: MouseEvent) => {
      const currentWorkspaceRect = workspaceRef.current?.getBoundingClientRect() ?? workspaceRect
      const widthFromRightEdge = currentWorkspaceRect.right - moveEvent.clientX - pointerOffset
      const next = Math.max(320, Math.min(maxArtifactWidth, widthFromRightEdge))
      setArtifactWidth(next)
    }

    const onMouseUp = () => {
      document.removeEventListener("mousemove", onMouseMove)
      document.removeEventListener("mouseup", onMouseUp)
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }

    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
    document.addEventListener("mousemove", onMouseMove)
    document.addEventListener("mouseup", onMouseUp)
  }, [artifactPaneWidth, maxArtifactWidth, setArtifactWidth])

  const renderArtifact = React.useMemo(() => {
    if (artifact.kind === 'activity') {
      return (
        <ActivityDashboard
          embedded
          showHeader={false}
          selectedScorecard={selectedScorecard}
          setSelectedScorecard={setSelectedScorecard}
          selectedScore={selectedScore}
          setSelectedScore={setSelectedScore}
        />
      )
    }

    if (artifact.kind === 'board') {
      return (
        <ArtifactPlaceholder
          icon={<KanbanSquare className="h-4 w-4" />}
          title="Board artifact"
          description="Kanbus-backed board artifacts will render here."
        />
      )
    }

    if (artifact.kind === 'report') {
      return (
        <ArtifactPlaceholder
          icon={<FileBarChart className="h-4 w-4" />}
          title="Report artifact"
          description="Interactive report blocks will render in this pane."
        />
      )
    }

    return null
  }, [artifact.kind, selectedScore, selectedScorecard])

  return (
    <div className="@container flex h-full flex-col overflow-hidden p-3">
      <div className="flex flex-wrap items-start justify-between gap-3 pb-3 flex-shrink-0">
        <div className="min-w-0 flex-1">
          <ScorecardContext
            selectedScorecard={selectedScorecard}
            setSelectedScorecard={setSelectedScorecard}
            selectedScore={selectedScore}
            setSelectedScore={setSelectedScore}
          />
        </div>
        <div className="shrink-0 self-start">
          <TaskDispatchButton config={actionsConfig} />
        </div>
      </div>

      <div ref={workspaceRef} className="flex w-full max-w-full min-h-0 flex-1 overflow-hidden rounded-md bg-background">
        <div className="w-0 min-w-0 flex-1 overflow-hidden">
          <ConsoleChatElementsAdapter
            procedureId={selectedProcedureId}
            accountId={effectiveAccountId ?? undefined}
            selectedSessionId={selectedSessionId}
            onSessionSelect={handleSelectSession}
          />
        </div>

        {artifact.isOpen && artifact.kind !== 'none' && (
          <>
            <div
              className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
              onMouseDown={startArtifactResize}
            >
              <div className="absolute inset-0 rounded-full transition-colors duration-150 group-hover:bg-accent" />
            </div>
            <aside
              ref={artifactPaneRef}
              className="h-full flex-shrink-0 border-l border-border bg-card/70 overflow-hidden"
              style={{ width: artifactPaneWidth, minWidth: 320, maxWidth: maxArtifactWidth }}
            >
              <div className="flex items-center justify-between border-b border-border px-3 py-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Activity className="h-4 w-4 text-muted-foreground" />
                  <span>{artifactTitle}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={collapseArtifact}
                    aria-label="Collapse artifact pane"
                  >
                    <PanelRightClose className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="h-[calc(100%-40px)] overflow-hidden">{renderArtifact}</div>
            </aside>
          </>
        )}

        {!artifact.isOpen && artifact.kind !== 'none' && (
          <div className="flex h-full items-start border-l border-border bg-card/40 px-1 pt-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={expandLastArtifact}
              aria-label="Expand artifact pane"
            >
              <PanelRightOpen className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

    </div>
  )
}
