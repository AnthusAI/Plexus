"use client"

import * as React from "react"
import Link from "next/link"
import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  GitBranch,
  PlayCircle,
  TestTube2,
} from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

type WorkflowStatus = "changed" | "queued" | "running" | "completed" | "failed" | "needs-validation"

type WorkflowLink = {
  label: string
  href: string
  ariaLabel: string
}

type WorkflowStep = {
  key: string
  title: string
  description: string
  status: WorkflowStatus
  links: WorkflowLink[]
}

type ScoreChangeAudit = {
  version_id?: string | null
  parent_version_id?: string | null
  version_url?: string | null
  parent_version_url?: string | null
}

type ConsoleScoreWorkflowSummaryProps = {
  metadata?: unknown
  toolOutput?: unknown
  toolName?: string | null
}

const coerceRecord = (value: unknown): Record<string, unknown> | null => {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  if (typeof value !== "string") {
    return null
  }
  const text = value.trim()
  if (!text) {
    return null
  }
  try {
    const parsed = JSON.parse(text)
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
  } catch {
    const responseMatch = text.match(/\n\nResponse:\n([\s\S]+)$/)
    if (responseMatch) {
      return coerceRecord(responseMatch[1].trim())
    }
  }
  return null
}

const coerceArray = (value: unknown): unknown[] => Array.isArray(value) ? value : []

const stringValue = (record: Record<string, unknown> | null, ...keys: string[]): string | null => {
  if (!record) {
    return null
  }
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "string" && value.trim()) {
      return value.trim()
    }
  }
  return null
}

const boolValue = (record: Record<string, unknown> | null, ...keys: string[]): boolean | null => {
  if (!record) {
    return null
  }
  for (const key of keys) {
    const value = record[key]
    if (typeof value === "boolean") {
      return value
    }
  }
  return null
}

const shortenId = (value: string | null | undefined): string => {
  if (!value) {
    return ""
  }
  return value.length > 12 ? `${value.slice(0, 8)}...` : value
}

const parseScoreChangeAudit = (metadata: unknown): ScoreChangeAudit | null => {
  const record = coerceRecord(metadata)
  const audit = coerceRecord(record?.score_change_audit)
  if (!audit) {
    return null
  }
  return {
    version_id: stringValue(audit, "version_id", "versionId"),
    parent_version_id: stringValue(audit, "parent_version_id", "parentVersionId"),
    version_url: stringValue(audit, "version_url", "versionUrl"),
    parent_version_url: stringValue(audit, "parent_version_url", "parentVersionUrl"),
  }
}

const outputRecords = (toolOutput: unknown): Record<string, unknown>[] => {
  const root = coerceRecord(toolOutput)
  if (!root) {
    return []
  }
  const records: Record<string, unknown>[] = [root]
  const value = root.value
  const dispatchResult = root.dispatch_result ?? root.dispatchResult
  const data = root.data

  for (const candidate of [value, dispatchResult, data]) {
    const record = coerceRecord(candidate)
    if (record) {
      records.push(record)
    }
    for (const item of coerceArray(candidate)) {
      const itemRecord = coerceRecord(item)
      if (itemRecord) {
        records.push(itemRecord)
      }
    }
  }
  return records
}

const apiCalls = (record: Record<string, unknown>): string[] => (
  coerceArray(record.api_calls)
    .filter((call): call is string => typeof call === "string")
)

const hasEvaluationContext = (record: Record<string, unknown>, toolName?: string | null): boolean => {
  const normalizedToolName = String(toolName || "").toLowerCase()
  return (
    normalizedToolName.includes("evaluation")
    || apiCalls(record).some((call) => call.startsWith("plexus.evaluation."))
    || [
      "evaluation_id",
      "evaluationId",
      "evaluation_type",
      "evaluationType",
      "evaluation_record_created",
      "metrics",
      "accuracy",
      "processed_items",
      "total_items",
    ].some((key) => key in record)
  )
}

const hasReportContext = (record: Record<string, unknown>, toolName?: string | null): boolean => {
  const normalizedToolName = String(toolName || "").toLowerCase()
  return (
    normalizedToolName.includes("report")
    || apiCalls(record).some((call) => call.startsWith("plexus.report."))
    || ["report_id", "reportId"].some((key) => key in record)
  )
}

const hasOptimizationContext = (record: Record<string, unknown>, toolName?: string | null): boolean => {
  const normalizedToolName = String(toolName || "").toLowerCase()
  return (
    normalizedToolName.includes("optimiz")
    || apiCalls(record).some((call) => call.includes("optimiz") || call.startsWith("plexus.procedure."))
    || ["procedure_id", "procedureId", "optimization_id", "optimizationId"].some((key) => key in record)
  )
}

const normalizeWorkflowStatus = (
  record: Record<string, unknown>,
  options: { hasEvaluationId?: boolean } = {},
): WorkflowStatus => {
  const hasEvaluationId = Boolean(options.hasEvaluationId)
  const status = stringValue(record, "status")?.toLowerCase() || ""
  const dispatchStatus = stringValue(record, "dispatch_status", "dispatchStatus")?.toLowerCase() || ""
  const joined = `${status} ${dispatchStatus}`
  if (/(fail|error|cancel)/.test(joined)) {
    return "failed"
  }
  if (/(complete|succeed|success|finished)/.test(joined)) {
    return "completed"
  }
  if (/(dispatching|dispatched|running|in_progress|processing)/.test(joined)) {
    return "running"
  }
  if (/(queued|pending)/.test(joined)) {
    return "queued"
  }
  return hasEvaluationId ? "completed" : "queued"
}

const statusLabel = (status: WorkflowStatus): string => {
  switch (status) {
    case "changed":
      return "Changed"
    case "queued":
      return "Queued"
    case "running":
      return "Running"
    case "completed":
      return "Completed"
    case "failed":
      return "Failed"
    case "needs-validation":
      return "Needs validation"
  }
}

const statusIcon = (status: WorkflowStatus) => {
  switch (status) {
    case "changed":
      return <GitBranch className="h-4 w-4" />
    case "queued":
      return <Clock3 className="h-4 w-4" />
    case "running":
      return <PlayCircle className="h-4 w-4" />
    case "completed":
      return <CheckCircle2 className="h-4 w-4" />
    case "failed":
      return <AlertCircle className="h-4 w-4" />
    case "needs-validation":
      return <TestTube2 className="h-4 w-4" />
  }
}

const statusClassName = (status: WorkflowStatus): string => {
  switch (status) {
    case "changed":
      return "bg-blue-500/10 text-blue-700 dark:text-blue-300"
    case "queued":
      return "bg-amber-500/10 text-amber-700 dark:text-amber-300"
    case "running":
      return "bg-cyan-500/10 text-cyan-700 dark:text-cyan-300"
    case "completed":
      return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
    case "failed":
      return "bg-destructive/10 text-destructive"
    case "needs-validation":
      return "bg-neutral text-primary-foreground"
  }
}

const buildScoreChangeStep = (audit: ScoreChangeAudit | null): WorkflowStep | null => {
  if (!audit?.version_id && !audit?.version_url) {
    return null
  }
  const links: WorkflowLink[] = []
  if (audit.parent_version_url) {
    links.push({
      label: "Parent version",
      href: audit.parent_version_url,
      ariaLabel: "Open workflow parent score version",
    })
  }
  if (audit.version_url) {
    links.push({
      label: "Candidate version",
      href: audit.version_url,
      ariaLabel: "Open workflow candidate score version",
    })
  }
  return {
    key: `score:${audit.version_id || audit.version_url}`,
    title: "Score version changed",
    description: `Candidate ${shortenId(audit.version_id) || "version"} created${audit.parent_version_id ? ` from ${shortenId(audit.parent_version_id)}` : ""}.`,
    status: "changed",
    links,
  }
}

const buildEvaluationStep = (
  record: Record<string, unknown>,
  toolName?: string | null,
): WorkflowStep | null => {
  if (!hasEvaluationContext(record, toolName)) {
    return null
  }
  const evaluationId = stringValue(record, "evaluation_id", "evaluationId")
    || (hasEvaluationContext(record, toolName) ? stringValue(record, "id") : null)
  const taskId = stringValue(record, "task_id", "taskId")
  const evaluationRecordCreated = boolValue(record, "evaluation_record_created", "evaluationRecordCreated")
  const hasStatusSignal = Boolean(stringValue(record, "status", "dispatch_status", "dispatchStatus"))
  if (!evaluationId && !taskId && !hasStatusSignal && evaluationRecordCreated === null) {
    return null
  }
  const status = normalizeWorkflowStatus(record, { hasEvaluationId: Boolean(evaluationId) })
  const evaluationType = stringValue(record, "evaluation_type", "evaluationType")
  const scoreVersionId = stringValue(record, "score_version_id", "scoreVersionId", "version_id", "versionId")
  const links: WorkflowLink[] = []
  if (taskId) {
    links.push({
      label: "Task",
      href: `/lab/tasks/${taskId}`,
      ariaLabel: "Open workflow evaluation task",
    })
  }
  if (evaluationId) {
    links.push({
      label: "Evaluation",
      href: `/lab/evaluations/${evaluationId}`,
      ariaLabel: "Open workflow evaluation",
    })
  }

  const missingEvaluationRecord = taskId && !evaluationId && evaluationRecordCreated === false
  return {
    key: `evaluation:${evaluationId || taskId || JSON.stringify(record).slice(0, 80)}`,
    title: status === "completed" ? "Evaluation available" : "Evaluation queued",
    description: missingEvaluationRecord
      ? "Task queued; evaluation record not created yet."
      : `${evaluationType ? `${evaluationType} evaluation` : "Evaluation"} ${statusLabel(status).toLowerCase()}${scoreVersionId ? ` for version ${shortenId(scoreVersionId)}` : ""}.`,
    status,
    links,
  }
}

const buildReportStep = (
  record: Record<string, unknown>,
  toolName?: string | null,
): WorkflowStep | null => {
  if (!hasReportContext(record, toolName)) {
    return null
  }
  const reportId = stringValue(record, "report_id", "reportId")
  const taskId = stringValue(record, "task_id", "taskId")
  if (!reportId && !taskId && !stringValue(record, "status", "dispatch_status", "dispatchStatus")) {
    return null
  }
  const status = normalizeWorkflowStatus(record, { hasEvaluationId: Boolean(reportId) })
  const links: WorkflowLink[] = []
  if (taskId) {
    links.push({ label: "Task", href: `/lab/tasks/${taskId}`, ariaLabel: "Open workflow report task" })
  }
  if (reportId) {
    links.push({ label: "Report", href: `/lab/reports/${reportId}`, ariaLabel: "Open workflow report" })
  }
  return {
    key: `report:${reportId || taskId || JSON.stringify(record).slice(0, 80)}`,
    title: reportId ? "Report available" : "Report task queued",
    description: `Report ${statusLabel(status).toLowerCase()}.`,
    status,
    links,
  }
}

const buildOptimizationStep = (
  record: Record<string, unknown>,
  toolName?: string | null,
): WorkflowStep | null => {
  if (!hasOptimizationContext(record, toolName)) {
    return null
  }
  const taskId = stringValue(record, "task_id", "taskId")
  const procedureId = stringValue(record, "procedure_id", "procedureId", "optimization_id", "optimizationId")
  if (!procedureId && !taskId && !stringValue(record, "status", "dispatch_status", "dispatchStatus")) {
    return null
  }
  const status = normalizeWorkflowStatus(record, { hasEvaluationId: Boolean(procedureId) })
  const links: WorkflowLink[] = []
  if (taskId) {
    links.push({ label: "Task", href: `/lab/tasks/${taskId}`, ariaLabel: "Open workflow optimization task" })
  }
  if (procedureId) {
    links.push({ label: "Procedure", href: `/lab/procedures/${procedureId}`, ariaLabel: "Open workflow procedure" })
  }
  return {
    key: `optimization:${procedureId || taskId || JSON.stringify(record).slice(0, 80)}`,
    title: "Optimization workflow",
    description: `Optimization ${statusLabel(status).toLowerCase()}.`,
    status,
    links,
  }
}

const dedupeSteps = (steps: WorkflowStep[]): WorkflowStep[] => {
  const seen = new Set<string>()
  return steps.filter((step) => {
    if (seen.has(step.key)) {
      return false
    }
    seen.add(step.key)
    return true
  })
}

const buildWorkflowSteps = ({
  metadata,
  toolOutput,
  toolName,
}: ConsoleScoreWorkflowSummaryProps): WorkflowStep[] => {
  const steps: WorkflowStep[] = []
  const scoreStep = buildScoreChangeStep(parseScoreChangeAudit(metadata))
  if (scoreStep) {
    steps.push(scoreStep)
  }

  for (const record of outputRecords(toolOutput)) {
    const evaluationStep = buildEvaluationStep(record, toolName)
    if (evaluationStep) {
      steps.push(evaluationStep)
    }
    const reportStep = buildReportStep(record, toolName)
    if (reportStep) {
      steps.push(reportStep)
    }
    const optimizationStep = buildOptimizationStep(record, toolName)
    if (optimizationStep) {
      steps.push(optimizationStep)
    }
  }

  const hasScoreChange = Boolean(scoreStep)
  const hasValidation = steps.some((step) => step.key.startsWith("evaluation:"))
  if (hasScoreChange && !hasValidation) {
    steps.push({
      key: "validation:missing",
      title: "No validation run found",
      description: "No validation run found in this chat yet.",
      status: "needs-validation",
      links: [],
    })
  }

  if (steps.length) {
    const terminal = steps[steps.length - 1]
    steps.push({
      key: "next-action",
      title: "Next action",
      description: nextActionText(steps, terminal),
      status: terminal.status === "failed" ? "failed" : "queued",
      links: [],
    })
  }

  return dedupeSteps(steps)
}

const nextActionText = (steps: WorkflowStep[], terminal: WorkflowStep): string => {
  if (steps.some((step) => step.key === "validation:missing")) {
    return "Run a count-based feedback evaluation before comparing or promoting this candidate."
  }
  if (terminal.status === "queued") {
    return "Watch the task until it dispatches or creates a durable result."
  }
  if (terminal.status === "running") {
    return "Wait for completion before comparing results."
  }
  if (terminal.status === "failed") {
    return "Inspect the failed task or tool output before retrying."
  }
  return "Review the result, then decide whether to edit again, evaluate more, optimize, or promote explicitly."
}

export function ConsoleScoreWorkflowSummary(props: ConsoleScoreWorkflowSummaryProps) {
  const steps = React.useMemo(() => buildWorkflowSteps(props), [props.metadata, props.toolName, props.toolOutput])

  if (!steps.length) {
    return null
  }

  return (
    <div className="rounded-lg bg-muted/50 p-3" data-testid="console-score-workflow-summary">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="text-sm font-semibold">Score workflow</div>
        <Badge variant="secondary" className="shrink-0 text-[11px]">
          {steps.length} steps
        </Badge>
      </div>
      <div className="space-y-2">
        {steps.map((step) => (
          <div key={step.key} className="rounded-md bg-background/75 p-2" data-testid={`console-score-workflow-step-${step.status}`}>
            <div className="flex items-start gap-2">
              <div className={cn("mt-0.5 rounded-full p-1", statusClassName(step.status))}>
                {statusIcon(step.status)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-sm font-medium">{step.title}</div>
                  <Badge variant="secondary" className={cn("text-[11px] font-normal", statusClassName(step.status))}>
                    {statusLabel(step.status)}
                  </Badge>
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">{step.description}</div>
                {step.links.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {step.links.map((link) => (
                      <Link
                        key={`${step.key}:${link.href}:${link.label}`}
                        href={link.href}
                        aria-label={link.ariaLabel}
                        className="inline-flex items-center gap-1 rounded-md bg-card px-2 py-1 text-xs font-medium text-foreground hover:bg-card/80"
                      >
                        {link.label}
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
