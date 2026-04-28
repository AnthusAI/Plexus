"use client"

import * as React from "react"
import { DiffEditor, type Monaco } from "@monaco-editor/react"
import { GitCompareArrows } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Timestamp } from "@/components/ui/timestamp"
import {
  applyMonacoTheme,
  configureYamlLanguage,
  defineCustomMonacoThemes,
  getCommonMonacoOptions,
  setupMonacoThemeWatcher,
} from "@/lib/monaco-theme"
import type { ScoreVersion } from "./score-component"

interface ScoreVersionDiffDialogProps {
  isOpen: boolean
  onClose: () => void
  versions: ScoreVersion[]
  selectedVersionId?: string
  championVersionId?: string
  initialLeftVersionId?: string
  initialRightVersionId?: string
}

const versionLabel = (version?: ScoreVersion) => {
  if (!version) return "Select version"
  return version.note || `Version ${version.id.slice(0, 8)}`
}

const findDefaultLeftVersionId = (
  versions: ScoreVersion[],
  selectedVersionId?: string,
  championVersionId?: string
) => {
  if (!selectedVersionId) return championVersionId || versions[0]?.id
  if (selectedVersionId !== championVersionId) return championVersionId || versions[0]?.id
  const selected = versions.find(version => version.id === selectedVersionId)
  return selected?.parentVersionId || versions.find(version => version.id !== selectedVersionId)?.id || selectedVersionId
}

export function ScoreVersionDiffDialog({
  isOpen,
  onClose,
  versions,
  selectedVersionId,
  championVersionId,
  initialLeftVersionId,
  initialRightVersionId,
}: ScoreVersionDiffDialogProps) {
  const sortedVersions = React.useMemo(
    () => [...versions].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()),
    [versions]
  )
  const [leftVersionId, setLeftVersionId] = React.useState<string | undefined>()
  const [rightVersionId, setRightVersionId] = React.useState<string | undefined>()

  React.useEffect(() => {
    if (!isOpen) return
    setLeftVersionId(initialLeftVersionId || findDefaultLeftVersionId(sortedVersions, selectedVersionId, championVersionId))
    setRightVersionId(initialRightVersionId || selectedVersionId || championVersionId || sortedVersions[0]?.id)
  }, [championVersionId, initialLeftVersionId, initialRightVersionId, isOpen, selectedVersionId, sortedVersions])

  const leftVersion = sortedVersions.find(version => version.id === leftVersionId)
  const rightVersion = sortedVersions.find(version => version.id === rightVersionId)

  const handleEditorMount = (_editor: unknown, monaco: Monaco) => {
    defineCustomMonacoThemes(monaco)
    applyMonacoTheme(monaco)
    setupMonacoThemeWatcher(monaco)
    configureYamlLanguage(monaco)
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-[min(96vw,1400px)] h-[86vh] bg-card border-0 p-0 overflow-hidden flex flex-col">
        <DialogHeader className="px-4 py-3 bg-card">
          <DialogTitle className="flex items-center gap-2 text-base">
            <GitCompareArrows className="h-4 w-4" />
            Compare Score Versions
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col min-h-0 flex-1 bg-background p-3 gap-3">
          <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] gap-3 items-end">
            <VersionSelect
              label="Left version"
              value={leftVersionId}
              onValueChange={setLeftVersionId}
              versions={sortedVersions}
              championVersionId={championVersionId}
            />
            <Button
              variant="secondary"
              className="h-9 justify-self-center"
              onClick={() => {
                setLeftVersionId(rightVersionId)
                setRightVersionId(leftVersionId)
              }}
              disabled={!leftVersionId || !rightVersionId}
            >
              <GitCompareArrows className="mr-2 h-4 w-4" />
              Swap
            </Button>
            <VersionSelect
              label="Right version"
              value={rightVersionId}
              onValueChange={setRightVersionId}
              versions={sortedVersions}
              championVersionId={championVersionId}
            />
          </div>

          <Tabs defaultValue="code" className="flex-1 min-h-0 flex flex-col">
            <TabsList className="h-auto p-0 bg-card justify-start">
              <TabsTrigger value="code" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-4 border-transparent data-[state=active]:border-primary rounded-none px-3 py-2">Code</TabsTrigger>
              <TabsTrigger value="guidelines" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-4 border-transparent data-[state=active]:border-primary rounded-none px-3 py-2">Guidelines</TabsTrigger>
            </TabsList>
            <TabsContent value="code" className="flex-1 min-h-0 mt-0">
              <DiffEditor
                height="100%"
                language="yaml"
                original={leftVersion?.configuration || ""}
                modified={rightVersion?.configuration || ""}
                onMount={handleEditorMount}
                options={{
                  ...getCommonMonacoOptions(),
                  readOnly: true,
                  renderSideBySide: true,
                  automaticLayout: true,
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                }}
              />
            </TabsContent>
            <TabsContent value="guidelines" className="flex-1 min-h-0 mt-0">
              <DiffEditor
                height="100%"
                language="markdown"
                original={leftVersion?.guidelines || ""}
                modified={rightVersion?.guidelines || ""}
                onMount={handleEditorMount}
                options={{
                  ...getCommonMonacoOptions(),
                  readOnly: true,
                  renderSideBySide: true,
                  automaticLayout: true,
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                }}
              />
            </TabsContent>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function VersionSelect({
  label,
  value,
  onValueChange,
  versions,
  championVersionId,
}: {
  label: string
  value?: string
  onValueChange: (value: string) => void
  versions: ScoreVersion[]
  championVersionId?: string
}) {
  return (
    <div className="space-y-1 min-w-0">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className="w-full min-w-0 bg-card border-0">
          <SelectValue placeholder="Select version" />
        </SelectTrigger>
        <SelectContent className="bg-card border-0">
          {versions.map((version) => (
            <SelectItem key={version.id} value={version.id}>
              <div className="flex flex-col">
                <span>{versionLabel(version)}{version.id === championVersionId ? " (champion)" : ""}</span>
                <span className="text-xs text-muted-foreground">
                  <Timestamp time={version.createdAt} variant="relative" showIcon={false} className="text-xs" />
                </span>
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
