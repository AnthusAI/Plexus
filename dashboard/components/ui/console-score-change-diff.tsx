"use client"

import * as React from "react"
import { DiffEditor, type Monaco } from "@monaco-editor/react"
import Link from "next/link"
import { ChevronDown, ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  applyMonacoTheme,
  configureYamlLanguage,
  defineCustomMonacoThemes,
  getCommonMonacoOptions,
  setupMonacoThemeWatcher,
} from "@/lib/monaco-theme"

type ScoreDiffEntry = {
  kind?: string | null
  language?: string | null
  original?: string | null
  modified?: string | null
  unified_diff?: string | null
  has_changes?: boolean
  original_label?: string | null
  modified_label?: string | null
  original_version_id?: string | null
  modified_version_id?: string | null
  original_url?: string | null
  modified_url?: string | null
  truncated?: boolean
}

type ScoreChangeAudit = {
  version_id?: string | null
  parent_version_id?: string | null
  version_url?: string | null
  parent_version_url?: string | null
  diffs?: {
    code?: ScoreDiffEntry | null
    guidelines?: ScoreDiffEntry | null
  }
}

const coerceRecord = (value: unknown): Record<string, unknown> | null => {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  if (typeof value !== "string") {
    return null
  }
  const text = value.trim()
  if (!text.startsWith("{") || !text.endsWith("}")) {
    return null
  }
  try {
    const parsed = JSON.parse(text)
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
  } catch {
    return null
  }
  return null
}

const parseScoreChangeAudit = (metadata: unknown): ScoreChangeAudit | null => {
  const record = coerceRecord(metadata)
  if (!record) {
    return null
  }
  const audit = coerceRecord(record.score_change_audit)
  if (!audit) {
    return null
  }
  const diffs = coerceRecord(audit.diffs)
  return {
    version_id: typeof audit.version_id === "string" ? audit.version_id : null,
    parent_version_id: typeof audit.parent_version_id === "string" ? audit.parent_version_id : null,
    version_url: typeof audit.version_url === "string" ? audit.version_url : null,
    parent_version_url: typeof audit.parent_version_url === "string" ? audit.parent_version_url : null,
    diffs: diffs
      ? {
          code: coerceRecord(diffs.code) as ScoreDiffEntry | null,
          guidelines: coerceRecord(diffs.guidelines) as ScoreDiffEntry | null,
        }
      : undefined,
  }
}

const handleDiffEditorMount = (_editor: unknown, monaco: Monaco) => {
  defineCustomMonacoThemes(monaco)
  applyMonacoTheme(monaco)
  setupMonacoThemeWatcher(monaco)
  configureYamlLanguage(monaco)
}

const shortenId = (value: string | null | undefined): string => {
  if (!value) {
    return ""
  }
  return value.length > 12 ? `${value.slice(0, 8)}...` : value
}

export function ConsoleScoreChangeDiff({ metadata }: { metadata: unknown }) {
  const audit = React.useMemo(() => parseScoreChangeAudit(metadata), [metadata])
  const codeDiff = audit?.diffs?.code
  const guidelinesDiff = audit?.diffs?.guidelines

  const tabs = React.useMemo(() => {
    const items: Array<{ key: "code" | "guidelines"; label: string; language: "yaml" | "markdown"; diff: ScoreDiffEntry }> = []
    if (codeDiff) {
      items.push({ key: "code", label: "Code", language: "yaml", diff: codeDiff })
    }
    if (guidelinesDiff) {
      items.push({ key: "guidelines", label: "Guidelines", language: "markdown", diff: guidelinesDiff })
    }
    return items
  }, [codeDiff, guidelinesDiff])

  const [isOpen, setIsOpen] = React.useState(false)
  const [activeTab, setActiveTab] = React.useState<"code" | "guidelines">("code")

  React.useEffect(() => {
    if (!tabs.length) {
      return
    }
    if (!tabs.some((tab) => tab.key === activeTab)) {
      setActiveTab(tabs[0].key)
    }
  }, [activeTab, tabs])

  if (!audit || tabs.length === 0) {
    return null
  }

  const parentHref = audit.parent_version_url || tabs[0]?.diff.original_url || null
  const updatedHref = audit.version_url || tabs[0]?.diff.modified_url || null
  const parentId = audit.parent_version_id || tabs[0]?.diff.original_version_id || null
  const updatedId = audit.version_id || tabs[0]?.diff.modified_version_id || null

  return (
    <div className="rounded-lg border border-border/70 bg-card/70" data-testid="console-score-change-diff">
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            className="h-auto w-full justify-between rounded-lg px-3 py-2 text-left"
            aria-expanded={isOpen}
            data-testid="console-score-change-diff-trigger"
          >
            <span className="flex min-w-0 items-center gap-2">
              {isOpen ? (
                <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
              <span className="truncate text-sm font-medium">Score version changes</span>
            </span>
            <span className="ml-3 shrink-0 text-xs text-muted-foreground">
              {tabs.some((tab) => tab.diff.has_changes) ? "Changed" : "No changes"}
            </span>
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="space-y-3 px-3 pb-3">
            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              {parentHref ? (
                <Link href={parentHref} className="underline" aria-label="Open previous score version">
                  Previous score version
                </Link>
              ) : (
                <span>Previous score version</span>
              )}
              {parentId ? <span className="font-mono">{shortenId(parentId)}</span> : null}
              {updatedHref ? (
                <Link href={updatedHref} className="underline" aria-label="Open updated score version">
                  Updated score version
                </Link>
              ) : (
                <span>Updated score version</span>
              )}
              {updatedId ? <span className="font-mono">{shortenId(updatedId)}</span> : null}
            </div>

            <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as "code" | "guidelines")} className="space-y-2">
              <TabsList className="h-auto p-0 bg-transparent justify-start">
                {tabs.map((tab) => (
                  <TabsTrigger
                    key={tab.key}
                    value={tab.key}
                    className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-primary rounded-none px-2.5 py-1.5"
                  >
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>
              {tabs.map((tab) => {
                const original = tab.diff.original || ""
                const modified = tab.diff.modified || ""
                const hasText = Boolean(original || modified)
                return (
                  <TabsContent key={tab.key} value={tab.key} className="mt-0">
                    {isOpen && hasText ? (
                      <div className="h-[320px] overflow-hidden rounded-lg bg-background" data-testid={`console-score-change-diff-${tab.key}`}>
                        <DiffEditor
                          height="100%"
                          language={tab.language}
                          original={original}
                          modified={modified}
                          onMount={handleDiffEditorMount}
                          options={{
                            ...getCommonMonacoOptions(),
                            readOnly: true,
                            renderSideBySide: true,
                            automaticLayout: true,
                            minimap: { enabled: false },
                            scrollBeyondLastLine: false,
                          }}
                        />
                      </div>
                    ) : (
                      <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-background p-3 text-xs text-foreground">
                        {tab.diff.unified_diff || "No diff content available."}
                      </pre>
                    )}
                    {tab.diff.truncated ? (
                      <div className="mt-2 text-xs text-muted-foreground">
                        Diff content is truncated for chat display.
                      </div>
                    ) : null}
                  </TabsContent>
                )
              })}
            </Tabs>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
