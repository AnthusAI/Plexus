"use client"

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { generateClient } from "aws-amplify/data"

import type { Schema } from "@/amplify/data/resource"
import { FeedEmpty, FeedError, FeedLoading } from "@/components/feed-presentation"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Spinner } from "@/components/ui/spinner"
import { Timestamp } from "@/components/ui/timestamp"
import { getMessageAttributionMetadata } from "@/components/ui/chat-message-user-avatar"
import { getControlEnvelope, isPendingHumanInteraction, parseMessageMetadata } from "@/lib/procedure-hitl"
import { cn } from "@/lib/utils"
import { getCurrentUserAttribution } from "@/utils/user-profile"

export type ActionInboxStatus = "OPEN" | "RESOLVED" | "STALE" | "EXPIRED" | "CANCELLED"
export type ActionUpdateMilestone = "STARTED" | "COMPLETED" | "FAILED" | "BLOCKED" | "APPROVAL_NEEDED" | "PROGRESS"
export type ActionUpdateSeverity = "INFO" | "WARNING" | "ERROR"

export interface PlexusResourceRef {
  system: "plexus" | string
  kind: "report" | "report_block" | "procedure" | "task" | "scorecard" | "score" | "score_version" | "evaluation" | string
  id: string
  label?: string | null
  relation?: string | null
  parentId?: string | null
  scorecardId?: string | null
  scoreId?: string | null
  revision?: string | null
}

export interface ActionInboxMessage {
  id: string
  accountId?: string | null
  createdByUserId?: string | null
  sessionId: string
  procedureId?: string | null
  role?: "USER" | "ASSISTANT" | "SYSTEM" | "TOOL" | string | null
  messageType?: "MESSAGE" | "TOOL_CALL" | "TOOL_RESPONSE" | string | null
  humanInteraction?: string | null
  content: string
  metadata?: unknown
  parentMessageId?: string | null
  responseStatus?: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | string | null
  responseOwner?: string | null
  responseStartedAt?: string | null
  responseCompletedAt?: string | null
  responseError?: string | null
  createdAt: string
}

export interface CanonicalActionControl extends Record<string, unknown> {
  request_id: string
  procedure_id: string
  request_type: string
  action_key?: string
  title?: string
  prompt?: string
  message?: string
  kind?: string
  preconditions?: unknown
  precondition_fingerprint?: string
  evidence_fingerprint?: string
  expires_at?: string | null
  response_schema?: unknown
  ui_schema?: unknown
  resource_refs?: PlexusResourceRef[]
}

export interface ActionResponseCandidate {
  id: string
  value: unknown
  createdAt: string
  createdByUserId?: string | null
  accepted: boolean
}

export interface ActionInboxAction {
  id: string
  kind: string
  status: ActionInboxStatus
  title: string
  summary?: string | null
  createdAt: string
  control: CanonicalActionControl
  responseSchema?: unknown
  uiSchema?: unknown
  resourceRefs: PlexusResourceRef[]
  responseCandidates: ActionResponseCandidate[]
  acceptedResponseId?: string | null
  sourceMessage: ActionInboxMessage
}

export interface ActionUpdate {
  id: string
  eventKey: string
  milestone: ActionUpdateMilestone
  severity: ActionUpdateSeverity
  title: string
  summary?: string | null
  createdAt: string
  resourceRefs: PlexusResourceRef[]
}

export interface ActionInboxPage<T> {
  items: T[]
  nextCursor: string | null
}

export interface ActionInboxDataSource {
  listMessages(input: {
    accountId: string
    cursor?: string | null
    limit: number
  }): Promise<ActionInboxPage<ActionInboxMessage>>
  submitResponse(input: {
    action: ActionInboxAction
    response: Record<string, unknown>
  }): Promise<ActionInboxMessage>
}

type ChatMessageModel = {
  listChatMessageByAccountIdAndCreatedAt: (...args: any[]) => Promise<any>
  create: (...args: any[]) => Promise<any>
}

type ActionInboxAmplifyClient = {
  models: { ChatMessage: ChatMessageModel }
}

type AttributionProvider = () => Promise<{ createdByUserId?: string }>

const MESSAGE_SELECTION = [
  "id",
  "accountId",
  "createdByUserId",
  "sessionId",
  "procedureId",
  "role",
  "messageType",
  "humanInteraction",
  "content",
  "metadata",
  "parentMessageId",
  "responseStatus",
  "responseOwner",
  "responseStartedAt",
  "responseCompletedAt",
  "responseError",
  "createdAt",
]

let amplifyClient: ReturnType<typeof generateClient<Schema>> | null = null
const getAmplifyClient = () => (amplifyClient ??= generateClient<Schema>())

function asMessage(value: any): ActionInboxMessage {
  return {
    id: String(value.id),
    accountId: value.accountId,
    createdByUserId: value.createdByUserId,
    sessionId: String(value.sessionId),
    procedureId: value.procedureId,
    role: value.role,
    messageType: value.messageType,
    humanInteraction: value.humanInteraction,
    content: typeof value.content === "string" ? value.content : "",
    metadata: value.metadata,
    parentMessageId: value.parentMessageId,
    responseStatus: value.responseStatus,
    responseOwner: value.responseOwner,
    responseStartedAt: value.responseStartedAt,
    responseCompletedAt: value.responseCompletedAt,
    responseError: value.responseError,
    createdAt: String(value.createdAt),
  }
}

/** Uses only the existing ChatMessage account index and ChatMessage.create operation. */
export function createAmplifyActionInboxDataSource(
  client: ActionInboxAmplifyClient = getAmplifyClient() as ActionInboxAmplifyClient,
  attributionProvider: AttributionProvider = getCurrentUserAttribution,
  now: () => Date = () => new Date(),
): ActionInboxDataSource {
  return {
    async listMessages({ accountId, cursor, limit }) {
      const result = await client.models.ChatMessage.listChatMessageByAccountIdAndCreatedAt(
        {
          accountId,
          sortDirection: "DESC",
          limit,
          nextToken: cursor || undefined,
        },
        { selectionSet: MESSAGE_SELECTION },
      )
      if (result?.errors?.length) {
        throw new Error(result.errors.map((error: any) => error.message || String(error)).join("; "))
      }
      return {
        items: Array.isArray(result?.data) ? result.data.map(asMessage) : [],
        nextCursor: typeof result?.nextToken === "string" && result.nextToken ? result.nextToken : null,
      }
    },

    async submitResponse({ action, response }) {
      const pending = action.sourceMessage
      if (!pending.accountId || !pending.sessionId || !pending.procedureId) {
        throw new Error("The pending message is missing account, session, or procedure identity.")
      }
      const respondedAt = now().toISOString()
      const attribution = await attributionProvider()
      const control = action.control
      const metadata = {
        ...getMessageAttributionMetadata(attribution.createdByUserId),
        control: {
          request_id: control.request_id,
          procedure_id: control.procedure_id,
          request_type: control.request_type,
          ...(typeof control.action_key === "string" ? { action_key: control.action_key } : {}),
          ...(typeof control.precondition_fingerprint === "string"
            ? { precondition_fingerprint: control.precondition_fingerprint }
            : {}),
          ...(typeof control.evidence_fingerprint === "string"
            ? { evidence_fingerprint: control.evidence_fingerprint }
            : {}),
          value: response,
          responded_at: respondedAt,
        },
      }
      const input = {
        accountId: pending.accountId,
        sessionId: pending.sessionId,
        procedureId: pending.procedureId,
        parentMessageId: pending.id,
        role: "USER",
        messageType: "MESSAGE",
        humanInteraction: "RESPONSE",
        content: JSON.stringify({ value: response }),
        metadata: JSON.stringify(metadata),
        responseStatus: "PENDING",
        createdAt: respondedAt,
        ...attribution,
      }
      const result = await client.models.ChatMessage.create(input)
      if (result?.errors?.length) {
        throw new Error(result.errors.map((error: any) => error.message || String(error)).join("; "))
      }
      if (!result?.data?.id) {
        throw new Error("Failed to persist RESPONSE message.")
      }
      return asMessage({ ...input, ...result.data })
    },
  }
}

const DEFAULT_DATA_SOURCE = createAmplifyActionInboxDataSource()
const ActionInboxDataSourceContext = createContext<ActionInboxDataSource | null>(null)

export function ActionInboxDataSourceProvider({
  dataSource,
  children,
}: {
  dataSource: ActionInboxDataSource
  children: React.ReactNode
}) {
  return <ActionInboxDataSourceContext.Provider value={dataSource}>{children}</ActionInboxDataSourceContext.Provider>
}

const keyMilestones = new Set<ActionUpdateMilestone>([
  "STARTED",
  "COMPLETED",
  "FAILED",
  "BLOCKED",
  "APPROVAL_NEEDED",
])

const timeValue = (value: string) => {
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function newestFirst<T extends { createdAt: string }>(items: T[]): T[] {
  return [...items].sort((left, right) => timeValue(right.createdAt) - timeValue(left.createdAt))
}

function oldestFirst<T extends { createdAt: string; id: string }>(items: T[]): T[] {
  return [...items].sort((left, right) => timeValue(left.createdAt) - timeValue(right.createdAt) || left.id.localeCompare(right.id))
}

function uniqueById<T extends { id: string }>(items: T[]): T[] {
  return Array.from(new Map(items.map((item) => [item.id, item])).values())
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null
}

function resourceRefs(value: unknown): PlexusResourceRef[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is PlexusResourceRef => {
    const record = asRecord(item)
    return Boolean(record && typeof record.system === "string" && typeof record.kind === "string" && typeof record.id === "string")
  })
}

function canonicalControl(metadata: unknown): CanonicalActionControl | null {
  const base = getControlEnvelope(metadata)
  const parsed = parseMessageMetadata(metadata)
  const control = asRecord(parsed?.control)
  return base && control ? control as CanonicalActionControl : null
}

function responseValue(message: ActionInboxMessage): unknown {
  const control = asRecord(parseMessageMetadata(message.metadata)?.control)
  if (control && "value" in control) return control.value
  try {
    const parsed = JSON.parse(message.content)
    const record = asRecord(parsed)
    return record && "value" in record ? record.value : parsed
  } catch {
    return message.content
  }
}

function actionStatus(message: ActionInboxMessage, control: CanonicalActionControl, now: Date): ActionInboxStatus {
  if (message.humanInteraction === "CANCELLED") return "CANCELLED"
  if (message.humanInteraction === "TIMED_OUT") return "EXPIRED"
  if (message.responseStatus === "COMPLETED") return "RESOLVED"
  if (message.responseStatus === "FAILED") return "STALE"
  const expiresAt = stringValue(control.expires_at)
  if (expiresAt && timeValue(expiresAt) <= now.getTime()) return "EXPIRED"
  return "OPEN"
}

function updateSeverity(humanInteraction: string | null | undefined): ActionUpdateSeverity {
  if (humanInteraction === "ALERT_WARNING") return "WARNING"
  if (humanInteraction === "ALERT_ERROR" || humanInteraction === "ALERT_CRITICAL") return "ERROR"
  return "INFO"
}

export function keyMilestoneUpdates(updates: ActionUpdate[]): ActionUpdate[] {
  const latestByKey = new Map<string, ActionUpdate>()
  for (const item of newestFirst(updates)) {
    if (keyMilestones.has(item.milestone) && !latestByKey.has(item.eventKey)) {
      latestByKey.set(item.eventKey, item)
    }
  }
  return newestFirst(Array.from(latestByKey.values()))
}

export function buildActionInboxViewModel(messages: ActionInboxMessage[], now = new Date()): {
  actions: ActionInboxAction[]
  updates: ActionUpdate[]
} {
  const responseChildren = new Map<string, ActionInboxMessage[]>()
  for (const message of messages) {
    if (message.humanInteraction === "RESPONSE" && message.parentMessageId) {
      responseChildren.set(message.parentMessageId, [
        ...(responseChildren.get(message.parentMessageId) || []),
        message,
      ])
    }
  }

  const actions: ActionInboxAction[] = []
  const updates: ActionUpdate[] = []
  for (const message of uniqueById(messages)) {
    const control = canonicalControl(message.metadata)
    const isAction = isPendingHumanInteraction(message.humanInteraction)
      || message.humanInteraction === "CANCELLED"
      || message.humanInteraction === "TIMED_OUT"
    if (isAction && control) {
      const candidates = oldestFirst(responseChildren.get(message.id) || []).map((candidate) => ({
        id: candidate.id,
        value: responseValue(candidate),
        createdAt: candidate.createdAt,
        createdByUserId: candidate.createdByUserId,
        accepted: candidate.id === message.responseOwner,
      }))
      const title = stringValue(control.title)
        || stringValue(control.prompt)
        || message.content
        || "Action required"
      const prompt = stringValue(control.message) || stringValue(control.prompt)
      actions.push({
        id: message.id,
        kind: stringValue(control.kind) || control.request_type,
        status: actionStatus(message, control, now),
        title,
        summary: prompt && prompt !== title ? prompt : null,
        createdAt: message.createdAt,
        control,
        responseSchema: control.response_schema,
        uiSchema: control.ui_schema,
        resourceRefs: resourceRefs(control.resource_refs),
        responseCandidates: candidates,
        acceptedResponseId: stringValue(message.responseOwner),
        sourceMessage: message,
      })
      continue
    }

    const isUpdate = message.humanInteraction === "NOTIFICATION" || message.humanInteraction?.startsWith("ALERT_")
    if (!isUpdate) continue
    const metadata = parseMessageMetadata(message.metadata)
    const event = asRecord(metadata?.event)
    const updateControl = asRecord(metadata?.control)
    const milestoneRaw = stringValue(metadata?.milestone)
      || stringValue(event?.milestone)
      || stringValue(updateControl?.milestone)
    const eventKey = stringValue(metadata?.event_key)
      || stringValue(event?.event_key)
      || stringValue(updateControl?.event_key)
    if (!milestoneRaw || !eventKey || !keyMilestones.has(milestoneRaw as ActionUpdateMilestone)) continue
    updates.push({
      id: message.id,
      eventKey,
      milestone: milestoneRaw as ActionUpdateMilestone,
      severity: updateSeverity(message.humanInteraction),
      title: stringValue(metadata?.title) || stringValue(event?.title) || message.content || milestoneRaw,
      summary: stringValue(metadata?.summary) || stringValue(event?.summary),
      createdAt: message.createdAt,
      resourceRefs: resourceRefs(metadata?.resource_refs || event?.resource_refs),
    })
  }

  return { actions: newestFirst(actions), updates: keyMilestoneUpdates(updates) }
}

/** Returns a dashboard route only when the typed reference has enough context. */
export function derivePlexusResourceHref(reference: PlexusResourceRef): string | null {
  if (reference.system !== "plexus" || !reference.id) return null
  const id = encodeURIComponent(reference.id)
  switch (reference.kind) {
    case "report":
      return `/lab/reports/${id}`
    case "report_block":
      return reference.parentId ? `/lab/reports/${encodeURIComponent(reference.parentId)}` : null
    case "procedure":
      return `/lab/procedures/${id}`
    case "task":
      return `/lab/tasks/${id}`
    case "scorecard":
      return `/lab/scorecards/${id}`
    case "score":
      return reference.scorecardId
        ? `/lab/scorecards/${encodeURIComponent(reference.scorecardId)}/scores/${id}`
        : null
    case "score_version":
      return reference.scorecardId && reference.scoreId
        ? `/lab/scorecards/${encodeURIComponent(reference.scorecardId)}/scores/${encodeURIComponent(reference.scoreId)}/versions/${encodeURIComponent(reference.revision || reference.id)}`
        : null
    case "evaluation":
      return `/lab/evaluations/${id}`
    default:
      return null
  }
}

function ResourceLinks({ references = [] }: { references?: PlexusResourceRef[] }) {
  const links = references
    .map((reference) => ({ reference, href: derivePlexusResourceHref(reference) }))
    .filter((item): item is { reference: PlexusResourceRef; href: string } => Boolean(item.href))
  if (links.length === 0) return null
  return (
    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs">
      {links.map(({ reference, href }) => (
        <a key={`${reference.kind}:${reference.id}`} href={href} className="text-primary underline-offset-2 hover:underline">
          {reference.label || `Open ${reference.kind.replaceAll("_", " ")}`}
        </a>
      ))}
    </div>
  )
}

const actionStatusClass: Record<ActionInboxStatus, string> = {
  OPEN: "bg-primary/10 text-primary",
  RESOLVED: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  STALE: "bg-amber-500/10 text-amber-800 dark:text-amber-300",
  EXPIRED: "bg-muted text-muted-foreground",
  CANCELLED: "bg-muted text-muted-foreground",
}

function ActionStatusBadge({ status }: { status: ActionInboxStatus }) {
  return <Badge variant="secondary" className={cn("text-[10px]", actionStatusClass[status])}>{status[0]}{status.slice(1).toLowerCase()}</Badge>
}

type PrimitiveField = {
  key: string
  label: string
  description?: string
  required: boolean
  kind: "string" | "boolean" | "enum"
  options?: Array<{ label: string; value: string }>
}

type PortfolioTarget = {
  scorecardId: string
  scoreId: string
  scorecardName?: string
  scoreName?: string
}
type ResponseFormDescription =
  | { kind: "simple"; fields: PrimitiveField[] }
  | { kind: "portfolio"; targets: PortfolioTarget[]; decisionOptions: Array<{ label: string; value: string }> }
  | { kind: "unsupported" }

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function primitiveField(key: string, schema: unknown, required: boolean): PrimitiveField | null {
  const record = asRecord(schema)
  if (!record) return null
  const label = stringValue(record.title) || humanize(key)
  const description = stringValue(record.description) || undefined
  if (Array.isArray(record.enum) && record.enum.length > 0 && record.enum.every((item) => typeof item === "string" || typeof item === "boolean")) {
    return {
      key,
      label,
      description,
      required,
      kind: "enum",
      options: record.enum.map((item) => ({ label: humanize(String(item)), value: String(item) })),
    }
  }
  if (record.type === "string") return { key, label, description, required, kind: "string" }
  if (record.type === "boolean") {
    return {
      key,
      label,
      description,
      required,
      kind: "boolean",
      options: [{ label: "Yes", value: "true" }, { label: "No", value: "false" }],
    }
  }
  return null
}

function describeResponseForm(action: ActionInboxAction): ResponseFormDescription {
  const schema = asRecord(action.responseSchema)
  const properties = asRecord(schema?.properties)
  if (!schema || schema.type !== "object" || !properties) return { kind: "unsupported" }

  const decisions = asRecord(properties.decisions)
  if (decisions) {
    const itemSchema = asRecord(decisions.items)
    const itemProperties = asRecord(itemSchema?.properties)
    const decision = primitiveField("decision", itemProperties?.decision, true)
    const preconditions = asRecord(action.control.preconditions)
    const targetsRaw = preconditions?.targets
    if (
      decisions.type !== "array"
      || itemSchema?.type !== "object"
      || !itemProperties
      || decision?.kind !== "enum"
      || !Array.isArray(targetsRaw)
      || targetsRaw.length === 0
      || targetsRaw.length > 5
    ) return { kind: "unsupported" }
    const targets: PortfolioTarget[] = []
    for (const targetRaw of targetsRaw) {
      const target = asRecord(targetRaw)
      const scorecardId = stringValue(target?.scorecard_id)
      const scoreId = stringValue(target?.score_id)
      if (!scorecardId || !scoreId) return { kind: "unsupported" }
      targets.push({
        scorecardId,
        scoreId,
        scorecardName: stringValue(target?.scorecard_name) || undefined,
        scoreName: stringValue(target?.score_name) || undefined,
      })
    }
    if (
      (typeof decisions.minItems === "number" && decisions.minItems !== targets.length)
      || (typeof decisions.maxItems === "number" && decisions.maxItems !== targets.length)
    ) return { kind: "unsupported" }
    return { kind: "portfolio", targets, decisionOptions: decision.options || [] }
  }

  const required = new Set(Array.isArray(schema.required) ? schema.required.filter((key): key is string => typeof key === "string") : [])
  const fields: PrimitiveField[] = []
  for (const [key, fieldSchema] of Object.entries(properties)) {
    const field = primitiveField(key, fieldSchema, required.has(key))
    if (!field) return { kind: "unsupported" }
    fields.push(field)
  }
  return fields.length > 0 ? { kind: "simple", fields } : { kind: "unsupported" }
}

function ChoiceField({
  name,
  label,
  description,
  options,
  value,
  required,
  onChange,
}: {
  name: string
  label: string
  description?: string
  options: Array<{ label: string; value: string }>
  value?: string
  required?: boolean
  onChange: (value: string) => void
}) {
  return (
    <fieldset>
      <legend className="text-xs font-medium text-foreground">{label}{required ? " *" : ""}</legend>
      {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
        {options.map((option) => (
          <label key={option.value} className="flex items-center gap-1.5 text-xs text-foreground">
            <input type="radio" name={name} value={option.value} checked={value === option.value} onChange={(event) => onChange(event.target.value)} />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function Responses({ action }: { action: ActionInboxAction }) {
  if (action.responseCandidates.length === 0) return null
  return (
    <div className="mt-3 bg-muted/50 p-2 text-xs">
      <p className="font-medium text-foreground">
        {action.responseCandidates.length} response {action.responseCandidates.length === 1 ? "candidate" : "candidates"}
      </p>
      <div className="mt-1 space-y-1">
        {action.responseCandidates.map((candidate) => (
          <div key={candidate.id} data-testid={`response-candidate-${candidate.id}`} className="flex items-center justify-between gap-2 text-muted-foreground">
            <span className="truncate font-mono">{candidate.id}</span>
            <span>{candidate.accepted ? "Accepted" : "Not accepted"}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ActionResponseForm({
  action,
  onSubmit,
}: {
  action: ActionInboxAction
  onSubmit: (response: Record<string, unknown>) => Promise<void>
}) {
  const description = useMemo(() => describeResponseForm(action), [action])
  const [values, setValues] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const alreadySubmitted = action.responseCandidates.length > 0

  if (action.status !== "OPEN") {
    return <p className="mt-3 text-xs text-muted-foreground">This action is {action.status.toLowerCase()} and can no longer be changed.</p>
  }
  if (alreadySubmitted) {
    return <p className="mt-3 text-xs text-muted-foreground">Response submitted. Acceptance is determined by the procedure.</p>
  }
  if (description.kind === "unsupported") {
    return <p className="mt-3 text-xs text-muted-foreground">This response schema is not supported by the Action Inbox yet.</p>
  }

  const submit = async () => {
    let response: Record<string, unknown>
    if (description.kind === "simple") {
      const missing = description.fields.find((field) => field.required && values[field.key] === undefined)
      if (missing) {
        setError(`${missing.label} is required.`)
        return
      }
      response = {}
      for (const field of description.fields) {
        if (values[field.key] === undefined) continue
        response[field.key] = field.kind === "boolean" ? values[field.key] === "true" : values[field.key]
      }
    } else {
      const missing = description.targets.find((target) => !values[`${target.scorecardId}:${target.scoreId}:decision`])
      if (missing) {
        setError(`A decision is required for ${missing.scoreId}.`)
        return
      }
      response = {
        decisions: description.targets.map((target) => ({
          scorecard_id: target.scorecardId,
          score_id: target.scoreId,
          decision: values[`${target.scorecardId}:${target.scoreId}:decision`],
          comment: values[`${target.scorecardId}:${target.scoreId}:comment`] || "",
        })),
      }
    }

    setIsSubmitting(true)
    setError(null)
    try {
      await onSubmit(response)
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Unable to submit this response.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mt-3 bg-muted/30 p-3">
      {description.kind === "simple" ? (
        <div className="space-y-3">
          {description.fields.map((field) => field.kind === "string" ? (
            <label key={field.key} className="block text-xs font-medium text-foreground">
              {field.label}{field.required ? " *" : ""}
              {field.description ? <span className="mt-0.5 block font-normal text-muted-foreground">{field.description}</span> : null}
              <textarea
                aria-label={field.label}
                className="mt-1.5 min-h-16 w-full resize-y rounded-[4px] bg-background px-2 py-1.5 text-xs outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={values[field.key] || ""}
                onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))}
              />
            </label>
          ) : (
            <ChoiceField
              key={field.key}
              name={`${action.id}:${field.key}`}
              label={field.label}
              description={field.description}
              options={field.options || []}
              value={values[field.key]}
              required={field.required}
              onChange={(value) => setValues((current) => ({ ...current, [field.key]: value }))}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {description.targets.map((target, index) => {
            const prefix = `${target.scorecardId}:${target.scoreId}`
            return (
              <section key={prefix} data-testid={`portfolio-target-${prefix}`} className="bg-background p-3">
                <p className="truncate text-xs text-muted-foreground">{target.scorecardName || "Scorecard"}</p>
                <p className="truncate text-sm font-medium text-foreground">{target.scoreName || `Optimization target ${index + 1}`}</p>
                <div className="mt-2">
                  <ChoiceField
                    name={`${action.id}:${prefix}:decision`}
                    label="Decision"
                    options={description.decisionOptions}
                    value={values[`${prefix}:decision`]}
                    required
                    onChange={(value) => setValues((current) => ({ ...current, [`${prefix}:decision`]: value }))}
                  />
                </div>
                <label className="mt-2 block text-xs font-medium text-foreground">
                  Comment
                  <textarea
                    aria-label="Comment"
                    className="mt-1.5 min-h-14 w-full resize-y rounded-[4px] bg-muted/40 px-2 py-1.5 text-xs outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    value={values[`${prefix}:comment`] || ""}
                    onChange={(event) => setValues((current) => ({ ...current, [`${prefix}:comment`]: event.target.value }))}
                  />
                </label>
              </section>
            )
          })}
        </div>
      )}
      {error ? <p role="alert" className="mt-2 text-xs text-destructive">{error}</p> : null}
      <Button className="mt-3" size="sm" onClick={submit} disabled={isSubmitting}>
        {isSubmitting ? <><Spinner size="sm" /> Submitting…</> : "Submit response"}
      </Button>
    </div>
  )
}

export interface ActionInboxViewProps {
  actions: ActionInboxAction[]
  updates: ActionUpdate[]
  isLoading?: boolean
  error?: string | null
  hasMoreMessages?: boolean
  isLoadingMore?: boolean
  onLoadMoreMessages?: () => void
  onSubmitResponse?: (action: ActionInboxAction, response: Record<string, unknown>) => Promise<void>
  className?: string
}

export function ActionInboxView({
  actions,
  updates,
  isLoading = false,
  error = null,
  hasMoreMessages = false,
  isLoadingMore = false,
  onLoadMoreMessages,
  onSubmitResponse,
  className,
}: ActionInboxViewProps) {
  const orderedActions = newestFirst(actions)
  const orderedUpdates = keyMilestoneUpdates(updates)
  if (isLoading) return <FeedLoading className={className} />
  if (error) return <FeedError className={className} title="Action Inbox is unavailable" detail={error} />

  return (
    <div className={cn("flex h-full min-h-0 flex-col bg-frame", className)}>
      <div className="bg-muted/40 px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Action Inbox</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">Decisions and key run updates for this account.</p>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-5 p-4">
          <section aria-labelledby="action-inbox-actions">
            <div className="mb-2 flex items-center justify-between">
              <h3 id="action-inbox-actions" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Actions</h3>
              <Badge variant="secondary" className="text-[10px]">{orderedActions.length}</Badge>
            </div>
            {orderedActions.length === 0 ? (
              <FeedEmpty title="No actions" description="New decisions will appear here." className="h-28 bg-muted/30" />
            ) : (
              <div className="space-y-2">
                {orderedActions.map((action) => (
                  <article key={action.id} data-testid={`action-inbox-action-${action.id}`} className="bg-background p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-foreground">{action.title}</p>
                        {action.summary ? <p className="mt-1 text-xs leading-5 text-muted-foreground">{action.summary}</p> : null}
                      </div>
                      <ActionStatusBadge status={action.status} />
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="uppercase tracking-wide">{action.kind}</span>
                      <span aria-hidden>·</span>
                      <Timestamp time={action.createdAt} variant="relative" />
                    </div>
                    <ResourceLinks references={action.resourceRefs} />
                    <Responses action={action} />
                    {onSubmitResponse
                      ? <ActionResponseForm action={action} onSubmit={(response) => onSubmitResponse(action, response)} />
                      : null}
                  </article>
                ))}
              </div>
            )}
          </section>

          <section aria-labelledby="action-inbox-updates">
            <h3 id="action-inbox-updates" className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Updates</h3>
            {orderedUpdates.length === 0 ? (
              <p className="text-xs text-muted-foreground">No key updates yet.</p>
            ) : (
              <div className="space-y-2 bg-muted/20 p-3">
                {orderedUpdates.map((item) => (
                  <article key={item.id} className="py-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-[10px]">{item.milestone.toLowerCase().replaceAll("_", " ")}</Badge>
                      <Timestamp time={item.createdAt} variant="relative" className="text-xs text-muted-foreground" />
                    </div>
                    <p className="mt-1 text-xs font-medium text-foreground">{item.title}</p>
                    {item.summary ? <p className="mt-0.5 text-xs text-muted-foreground">{item.summary}</p> : null}
                    <ResourceLinks references={item.resourceRefs} />
                  </article>
                ))}
              </div>
            )}
          </section>

          {hasMoreMessages && onLoadMoreMessages ? (
            <Button className="w-full" variant="outline" size="sm" onClick={onLoadMoreMessages} disabled={isLoadingMore}>
              {isLoadingMore ? "Loading…" : "Load older history"}
            </Button>
          ) : null}
        </div>
      </ScrollArea>
    </div>
  )
}

export interface ActionInboxProps {
  accountId: string
  dataSource?: ActionInboxDataSource
  className?: string
  pageSize?: number
}

export function ActionInbox({ accountId, dataSource, className, pageSize = 500 }: ActionInboxProps) {
  const providedDataSource = useContext(ActionInboxDataSourceContext)
  const resolvedDataSource = dataSource || providedDataSource || DEFAULT_DATA_SOURCE
  const [messages, setMessages] = useState<ActionInboxMessage[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const view = useMemo(() => buildActionInboxViewModel(messages), [messages])

  const loadInitial = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const page = await resolvedDataSource.listMessages({ accountId, cursor: null, limit: pageSize })
      setMessages(uniqueById(page.items))
      setNextCursor(page.nextCursor)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load Action Inbox messages.")
    } finally {
      setIsLoading(false)
    }
  }, [accountId, pageSize, resolvedDataSource])

  useEffect(() => {
    setMessages([])
    setNextCursor(null)
    void loadInitial()
  }, [loadInitial])

  const loadMoreMessages = async () => {
    if (!nextCursor || isLoadingMore) return
    setIsLoadingMore(true)
    try {
      const page = await resolvedDataSource.listMessages({ accountId, cursor: nextCursor, limit: pageSize })
      setMessages((current) => uniqueById([...current, ...page.items]))
      setNextCursor(page.nextCursor)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load older Action Inbox history.")
    } finally {
      setIsLoadingMore(false)
    }
  }

  const submitResponse = async (action: ActionInboxAction, response: Record<string, unknown>) => {
    const created = await resolvedDataSource.submitResponse({ action, response })
    setMessages((current) => uniqueById([...current, created]))
  }

  return (
    <ActionInboxView
      actions={view.actions}
      updates={view.updates}
      isLoading={isLoading}
      error={error}
      hasMoreMessages={Boolean(nextCursor)}
      isLoadingMore={isLoadingMore}
      onLoadMoreMessages={loadMoreMessages}
      onSubmitResponse={submitResponse}
      className={className}
    />
  )
}
