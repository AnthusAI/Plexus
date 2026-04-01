import { randomUUID } from "crypto";
import { SQSClient, SendMessageCommand } from "@aws-sdk/client-sqs";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const BUILTIN_PROCEDURE_RE = /^builtin:[a-z0-9][a-z0-9/_-]*$/i;

const GET_CHAT_SESSION_QUERY = `
  query GetChatSessionForConsoleStart($id: ID!) {
    getChatSession(id: $id) {
      id
      accountId
      procedureId
      status
    }
  }
`;

const GET_PROCEDURE_QUERY = `
  query GetProcedureForConsoleStart($id: ID!) {
    getProcedure(id: $id) {
      id
      accountId
      status
    }
  }
`;

const GET_CHAT_MESSAGE_QUERY = `
  query GetChatMessageForConsoleStart($id: ID!) {
    getChatMessage(id: $id) {
      id
      sessionId
      role
      messageType
      content
      metadata
      createdAt
    }
  }
`;

const LIST_SESSION_MESSAGES_QUERY = `
  query ListSessionMessagesForConsoleStart(
    $sessionId: String!
    $limit: Int
    $nextToken: String
  ) {
    listChatMessageBySessionIdAndCreatedAt(
      sessionId: $sessionId
      sortDirection: ASC
      limit: $limit
      nextToken: $nextToken
    ) {
      items {
        id
        role
        messageType
        content
        metadata
        createdAt
      }
      nextToken
    }
  }
`;

const CREATE_TASK_MUTATION = `
  mutation CreateTaskForConsoleRun($input: CreateTaskInput!) {
    createTask(input: $input) {
      id
      accountId
    }
  }
`;

const UPDATE_TASK_MUTATION = `
  mutation UpdateTaskAfterConsoleRunQueueError($input: UpdateTaskInput!) {
    updateTask(input: $input) {
      id
    }
  }
`;

const GET_TASK_QUERY = `
  query GetConsoleRunTaskById($id: ID!) {
    getTask(id: $id) {
      id
      status
      metadata
      createdAt
      updatedAt
    }
  }
`;

const LIST_RECENT_TASKS_QUERY = `
  query ListTaskByAccountIdAndUpdatedAtForConsoleRunDedup(
    $accountId: String!
    $updatedAt: ModelStringKeyConditionInput
    $limit: Int
    $nextToken: String
  ) {
    listTaskByAccountIdAndUpdatedAt(
      accountId: $accountId
      updatedAt: $updatedAt
      limit: $limit
      nextToken: $nextToken
    ) {
      items {
        id
        status
        target
        metadata
        createdAt
        updatedAt
      }
      nextToken
    }
  }
`;

const DEDUP_STATUSES = new Set(["PENDING", "RUNNING", "COMPLETED", "WAITING_FOR_HUMAN"]);
let runtimeGraphqlEndpoint = "";

function readHeaderValue(headers: Record<string, unknown>, name: string): string {
  const candidate = headers[name] ?? headers[name.toLowerCase()] ?? headers[name.toUpperCase()];
  if (Array.isArray(candidate)) {
    for (const item of candidate) {
      if (typeof item === "string" && item.trim()) {
        return item.trim();
      }
    }
    return "";
  }
  if (typeof candidate === "string") {
    return candidate.trim();
  }
  return "";
}

function endpointFromHostHeaderValue(rawHost: string): string {
  const trimmed = rawHost.trim();
  if (!trimmed) {
    return "";
  }
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed.endsWith("/graphql")
      ? trimmed
      : `${trimmed.replace(/\/+$/, "")}/graphql`;
  }
  const normalizedHost = trimmed.replace(/^\/+/, "").replace(/\/+$/, "");
  if (!normalizedHost) {
    return "";
  }
  return normalizedHost.endsWith("/graphql")
    ? `https://${normalizedHost}`
    : `https://${normalizedHost}/graphql`;
}

function setRuntimeGraphqlEndpoint(event: any): void {
  if (runtimeGraphqlEndpoint) {
    return;
  }
  const request = event?.request;
  if (!request || typeof request !== "object") {
    return;
  }
  const headers = (request as Record<string, unknown>).headers;
  if (!headers || typeof headers !== "object" || Array.isArray(headers)) {
    return;
  }
  const headerMap = headers as Record<string, unknown>;
  const hostCandidate = (
    readHeaderValue(headerMap, "x-forwarded-host")
    || readHeaderValue(headerMap, "host")
    || readHeaderValue(headerMap, ":authority")
  );
  const endpoint = endpointFromHostHeaderValue(hostCandidate);
  if (endpoint) {
    runtimeGraphqlEndpoint = endpoint;
  }
}

function resolveGraphqlEndpoint(): string {
  return (
    process.env.PLEXUS_API_URL ||
    process.env.API_GRAPHQLAPIENDPOINTOUTPUT ||
    runtimeGraphqlEndpoint ||
    ""
  ).trim();
}

function resolveAwsRegion(): string {
  return (
    process.env.AWS_REGION ||
    process.env.AWS_DEFAULT_REGION ||
    "us-east-1"
  ).trim();
}

function isValidId(value: unknown): value is string {
  return typeof value === "string" && UUID_RE.test(value.trim());
}

function isValidProcedureId(value: unknown): value is string {
  if (typeof value !== "string") {
    return false;
  }
  const trimmed = value.trim();
  return UUID_RE.test(trimmed) || BUILTIN_PROCEDURE_RE.test(trimmed);
}

function toIsoNow(): string {
  return new Date().toISOString();
}

function buildCanonicalTaskId(triggerMessageId: string): string {
  return `console-run-${triggerMessageId}`;
}

function normalizeInstrumentation(value: unknown): Record<string, unknown> {
  if (typeof value === "string") {
    const raw = value.trim();
    if (!raw) {
      return {};
    }
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      return {};
    }
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function extractTriggerMessageContent(instrumentation: Record<string, unknown>): string | null {
  const candidates = [
    instrumentation.client_user_message_text,
    instrumentation.trigger_message_content,
    instrumentation.message_text,
  ];
  for (const candidate of candidates) {
    if (typeof candidate === "string") {
      const normalized = candidate.trim();
      if (normalized) {
        return normalized;
      }
    }
  }
  return null;
}

type ConsoleHistoryEntry = {
  role: "USER" | "ASSISTANT";
  content: string;
};

const CLIENT_HISTORY_SNAPSHOT_LIMIT = 24;
const CLIENT_HISTORY_MAX_CONTENT_CHARS = 600;

function parseMetadataObject(value: unknown): Record<string, unknown> {
  if (!value) {
    return {};
  }
  if (typeof value === "string") {
    const raw = value.trim();
    if (!raw) {
      return {};
    }
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      return {};
    }
    return {};
  }
  if (typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function normalizeHistoryEntries(value: unknown): ConsoleHistoryEntry[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const normalized: ConsoleHistoryEntry[] = [];
  for (const entry of value) {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) {
      continue;
    }
    const record = entry as Record<string, unknown>;
    const roleRaw = String(record.role || "").trim().toUpperCase();
    if (roleRaw !== "USER" && roleRaw !== "ASSISTANT") {
      continue;
    }
    const messageTypeRaw = String(record.messageType || "").trim().toUpperCase();
    if (messageTypeRaw && messageTypeRaw !== "MESSAGE") {
      continue;
    }
    const contentRaw = String(record.content || "").trim();
    if (!contentRaw) {
      continue;
    }
    if (roleRaw === "ASSISTANT" && contentRaw === "Assistant turn completed.") {
      continue;
    }
    const content = contentRaw.length > CLIENT_HISTORY_MAX_CONTENT_CHARS
      ? `${contentRaw.slice(0, CLIENT_HISTORY_MAX_CONTENT_CHARS)}...`
      : contentRaw;
    normalized.push({
      role: roleRaw as "USER" | "ASSISTANT",
      content,
    });
  }
  if (normalized.length > CLIENT_HISTORY_SNAPSHOT_LIMIT) {
    return normalized.slice(normalized.length - CLIENT_HISTORY_SNAPSHOT_LIMIT);
  }
  return normalized;
}

function sameHistoryEntry(left: ConsoleHistoryEntry, right: ConsoleHistoryEntry): boolean {
  return left.role === right.role && left.content === right.content;
}

function dedupeAdjacentHistory(entries: ConsoleHistoryEntry[]): ConsoleHistoryEntry[] {
  const deduped: ConsoleHistoryEntry[] = [];
  for (const entry of entries) {
    const last = deduped[deduped.length - 1];
    if (last && sameHistoryEntry(last, entry)) {
      continue;
    }
    deduped.push(entry);
  }
  return deduped;
}

function mergeHistorySnapshots(
  serverHistory: ConsoleHistoryEntry[],
  clientHistory: ConsoleHistoryEntry[],
): ConsoleHistoryEntry[] {
  if (serverHistory.length > 0) {
    // Server history is authoritative. Client snapshots can become stale under
    // retries or delayed UI reconciliation and should not override persisted turns.
    return serverHistory.slice(-CLIENT_HISTORY_SNAPSHOT_LIMIT);
  }

  // Fallback for cold-start consistency windows where the session has not yet
  // materialized in the read query path.
  return clientHistory.slice(-CLIENT_HISTORY_SNAPSHOT_LIMIT);
}

function appendLatestUserIfMissing(
  history: ConsoleHistoryEntry[],
  latestUserMessage: string | null,
): ConsoleHistoryEntry[] {
  const latest = typeof latestUserMessage === "string" ? latestUserMessage.trim() : "";
  if (!latest) {
    return history;
  }
  const trimmed = latest.length > CLIENT_HISTORY_MAX_CONTENT_CHARS
    ? `${latest.slice(0, CLIENT_HISTORY_MAX_CONTENT_CHARS)}...`
    : latest;
  const copy = [...history];
  const last = copy[copy.length - 1];
  if (!last || last.role !== "USER" || last.content !== trimmed) {
    copy.push({ role: "USER", content: trimmed });
  }
  if (copy.length > CLIENT_HISTORY_SNAPSHOT_LIMIT) {
    return copy.slice(copy.length - CLIENT_HISTORY_SNAPSHOT_LIMIT);
  }
  return copy;
}

function parseTaskMetadata(raw: unknown): Record<string, unknown> {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    if (typeof raw === "string") {
      const trimmed = raw.trim();
      if (!trimmed) {
        return {};
      }
      try {
        const parsed = JSON.parse(trimmed);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          return parsed as Record<string, unknown>;
        }
      } catch {
        return {};
      }
    }
    return {};
  }
  return raw as Record<string, unknown>;
}

type GraphqlEnvelope<TData> = {
  data?: TData;
  errors?: Array<{ message?: string }>;
};

async function executeAppSyncGraphql<TData>(
  query: string,
  variables: Record<string, unknown>,
): Promise<TData> {
  const endpoint = resolveGraphqlEndpoint();
  const apiKey = (process.env.PLEXUS_API_KEY || "").trim();
  if (!endpoint || !apiKey) {
    throw new Error("Unable to resolve API URL and API key for startConsoleRun resolver");
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
    },
    body: JSON.stringify({ query, variables }),
  });

  const payload = (await response.json()) as GraphqlEnvelope<TData>;
  if (!response.ok) {
    throw new Error(`AppSync request failed (${response.status})`);
  }
  if (Array.isArray(payload.errors) && payload.errors.length > 0) {
    throw new Error(payload.errors[0]?.message || "AppSync request failed");
  }
  if (!payload.data) {
    throw new Error("AppSync request returned no data");
  }
  return payload.data;
}

async function findExistingConsoleRun(
  accountId: string,
  procedureId: string,
  sessionId: string,
  triggerMessageId: string,
): Promise<{ runId: string; taskId: string; queuedAt: string } | null> {
  const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  let nextToken: string | null | undefined = undefined;
  let scanned = 0;

  while (scanned < 300) {
    const result: {
      listTaskByAccountIdAndUpdatedAt: {
        items?: Array<{
          id?: string | null;
          status?: string | null;
          target?: string | null;
          metadata?: unknown;
          createdAt?: string | null;
          updatedAt?: string | null;
        } | null> | null;
        nextToken?: string | null;
      } | null;
    } = await executeAppSyncGraphql<{
      listTaskByAccountIdAndUpdatedAt: {
        items?: Array<{
          id?: string | null;
          status?: string | null;
          target?: string | null;
          metadata?: unknown;
          createdAt?: string | null;
          updatedAt?: string | null;
        } | null> | null;
        nextToken?: string | null;
      } | null;
    }>(LIST_RECENT_TASKS_QUERY, {
      accountId,
      updatedAt: { ge: cutoff },
      limit: 100,
      nextToken,
    });

    const page: {
      items?: Array<{
        id?: string | null;
        status?: string | null;
        target?: string | null;
        metadata?: unknown;
        createdAt?: string | null;
        updatedAt?: string | null;
      } | null> | null;
      nextToken?: string | null;
    } | null = result.listTaskByAccountIdAndUpdatedAt;
    const items = Array.isArray(page?.items) ? page?.items : [];
    scanned += items.length;

    for (const rawTask of items) {
      if (!rawTask?.id) {
        continue;
      }
      if ((rawTask.target || "").trim() !== `procedure/run/${procedureId}`) {
        continue;
      }

      const taskStatus = (rawTask.status || "").toUpperCase();
      if (!DEDUP_STATUSES.has(taskStatus)) {
        continue;
      }

      const metadata = parseTaskMetadata(rawTask.metadata);
      if ((metadata.dispatch_mode || "") !== "console_async_worker") {
        continue;
      }
      const consoleChat = metadata.console_chat;
      if (!consoleChat || typeof consoleChat !== "object" || Array.isArray(consoleChat)) {
        continue;
      }

      const consoleSessionId = String((consoleChat as Record<string, unknown>).session_id || "").trim();
      const consoleTriggerMessageId = String((consoleChat as Record<string, unknown>).trigger_message_id || "").trim();
      if (consoleSessionId !== sessionId || consoleTriggerMessageId !== triggerMessageId) {
        continue;
      }

      const runId = String((consoleChat as Record<string, unknown>).run_id || "").trim() || rawTask.id;
      const queuedAt =
        String((consoleChat as Record<string, unknown>).queued_at || "").trim()
        || String(rawTask.createdAt || "").trim()
        || String(rawTask.updatedAt || "").trim()
        || toIsoNow();

      return {
        runId,
        taskId: rawTask.id,
        queuedAt,
      };
    }

    nextToken = page?.nextToken;
    if (!nextToken) {
      break;
    }
  }

  return null;
}

export const handler = async (event: any) => {
  setRuntimeGraphqlEndpoint(event);
  const sessionId = event.arguments.sessionId?.trim();
  const procedureId = event.arguments.procedureId?.trim();
  const triggerMessageId = event.arguments.triggerMessageId?.trim();
  const queueUrl = (process.env.CONSOLE_RUN_QUEUE_URL || "").trim();
  const apiUrlForWorker = resolveGraphqlEndpoint();
  const apiKeyForWorker = (process.env.PLEXUS_API_KEY || "").trim();

  if (!isValidId(sessionId)) {
    throw new Error("startConsoleRun requires a valid sessionId");
  }
  if (!isValidProcedureId(procedureId)) {
    throw new Error("startConsoleRun requires a valid procedureId");
  }
  if (!isValidId(triggerMessageId)) {
    throw new Error("startConsoleRun requires a valid triggerMessageId");
  }
  if (!queueUrl) {
    throw new Error("CONSOLE_RUN_QUEUE_URL is not configured");
  }
  if (!apiUrlForWorker || !apiKeyForWorker) {
    throw new Error("Unable to resolve API URL and API key for console worker dispatch");
  }

  const sessionResult = await executeAppSyncGraphql<{
    getChatSession: {
      id: string;
      accountId?: string | null;
      procedureId?: string | null;
      status?: string | null;
    } | null;
  }>(GET_CHAT_SESSION_QUERY, { id: sessionId });

  const session = sessionResult.getChatSession;
  if (!session) {
    throw new Error(`Chat session ${sessionId} was not found`);
  }
  const accountId = (session.accountId || "").trim();
  if (!accountId) {
    throw new Error(`Chat session ${sessionId} is missing accountId`);
  }
  if (session.procedureId && session.procedureId !== procedureId) {
    throw new Error(
      `Session procedureId ${session.procedureId} does not match requested procedureId ${procedureId}`,
    );
  }

  if (!BUILTIN_PROCEDURE_RE.test(procedureId)) {
    const procedureResult = await executeAppSyncGraphql<{
      getProcedure: {
        id: string;
        accountId?: string | null;
      } | null;
    }>(GET_PROCEDURE_QUERY, { id: procedureId });
    const procedure = procedureResult.getProcedure;
    if (!procedure) {
      throw new Error(`Procedure ${procedureId} was not found`);
    }
    if ((procedure.accountId || "").trim() !== accountId) {
      throw new Error(`Procedure ${procedureId} is not available for this account`);
    }
  }

  const existingRun = await findExistingConsoleRun(accountId, procedureId, sessionId, triggerMessageId);
  if (existingRun) {
    return {
      runId: existingRun.runId,
      taskId: existingRun.taskId,
      accepted: true,
      queuedAt: existingRun.queuedAt,
    };
  }

  const runId = randomUUID();
  const canonicalTaskId = buildCanonicalTaskId(triggerMessageId);
  let taskId = canonicalTaskId;
  const queuedAt = toIsoNow();
  const clientInstrumentation = normalizeInstrumentation(event.arguments.clientInstrumentation);
  const providedClientHistory = normalizeHistoryEntries(clientInstrumentation.client_history_snapshot);

  const triggerMessageResult = await executeAppSyncGraphql<{
    getChatMessage: {
      id: string;
      sessionId?: string | null;
      role?: string | null;
      messageType?: string | null;
      content?: string | null;
      metadata?: unknown;
      createdAt?: string | null;
    } | null;
  }>(GET_CHAT_MESSAGE_QUERY, { id: triggerMessageId });
  const triggerMessage = triggerMessageResult.getChatMessage;
  if (!triggerMessage) {
    throw new Error(`Trigger message ${triggerMessageId} was not found`);
  }
  if ((triggerMessage.sessionId || "").trim() !== sessionId) {
    throw new Error(
      `Trigger message ${triggerMessageId} does not belong to session ${sessionId}`,
    );
  }

  // The trigger message record is authoritative for dispatch input.
  // Client instrumentation can be stale under retries/races; use it only as fallback.
  const triggerMessageContent = (() => {
    const canonicalTriggerContent = String(triggerMessage.content || "").trim();
    if (canonicalTriggerContent) {
      return canonicalTriggerContent;
    }
    return extractTriggerMessageContent(clientInstrumentation) || null;
  })();

  const serverHistoryMessages: Array<{
    role?: string | null;
    messageType?: string | null;
    content?: string | null;
    metadata?: unknown;
  }> = [];
  let nextMessageToken: string | null | undefined = undefined;
  do {
    const historyResult: {
      listChatMessageBySessionIdAndCreatedAt: {
        items?: Array<{
          role?: string | null;
          messageType?: string | null;
          content?: string | null;
          metadata?: unknown;
        } | null> | null;
        nextToken?: string | null;
      } | null;
    } = await executeAppSyncGraphql<{
      listChatMessageBySessionIdAndCreatedAt: {
        items?: Array<{
          role?: string | null;
          messageType?: string | null;
          content?: string | null;
          metadata?: unknown;
        } | null> | null;
        nextToken?: string | null;
      } | null;
    }>(LIST_SESSION_MESSAGES_QUERY, {
      sessionId,
      limit: 200,
      nextToken: nextMessageToken,
    });
    const page: {
      items?: Array<{
        role?: string | null;
        messageType?: string | null;
        content?: string | null;
        metadata?: unknown;
      } | null> | null;
      nextToken?: string | null;
    } | null = historyResult.listChatMessageBySessionIdAndCreatedAt;
    const pageItems = Array.isArray(page?.items) ? page?.items : [];
    for (const item of pageItems) {
      if (item && typeof item === "object") {
        serverHistoryMessages.push(item);
      }
    }
    nextMessageToken = page?.nextToken;
  } while (nextMessageToken && serverHistoryMessages.length < 800);

  const serverHistory = normalizeHistoryEntries(
    serverHistoryMessages.map((item) => {
      const metadata = parseMetadataObject(item.metadata);
      const streaming = parseMetadataObject(metadata.streaming);
      const streamingState = String(streaming.state || "").trim().toLowerCase();
      if (
        String(item.role || "").toUpperCase() === "ASSISTANT"
        && streamingState === "streaming"
      ) {
        return null;
      }
      return {
        role: item.role,
        messageType: item.messageType,
        content: item.content,
      };
    }).filter(Boolean),
  );

  let mergedHistory = mergeHistorySnapshots(serverHistory, providedClientHistory);
  mergedHistory = appendLatestUserIfMissing(mergedHistory, triggerMessageContent);
  const metadata = {
    dispatch_mode: "console_async_worker",
    console_chat: {
      session_id: sessionId,
      trigger_message_id: triggerMessageId,
      trigger_message_content: triggerMessageContent,
      queued_at: queuedAt,
      run_id: runId,
      instrumentation: {
        ...clientInstrumentation,
        client_history_snapshot: mergedHistory,
        queue_enqueued_at: queuedAt,
      },
    },
  };

  const canonicalTaskResult = await executeAppSyncGraphql<{
    getTask: {
      id?: string | null;
      status?: string | null;
      metadata?: unknown;
      createdAt?: string | null;
      updatedAt?: string | null;
    } | null;
  }>(GET_TASK_QUERY, { id: canonicalTaskId });

  const canonicalTask = canonicalTaskResult.getTask;
  if (canonicalTask?.id) {
    const canonicalMetadata = parseTaskMetadata(canonicalTask.metadata);
    const canonicalDispatchMode = String(canonicalMetadata.dispatch_mode || "");
    const canonicalConsoleChat = canonicalMetadata.console_chat;
    const canonicalSessionId = String(
      canonicalConsoleChat && typeof canonicalConsoleChat === "object" && !Array.isArray(canonicalConsoleChat)
        ? (canonicalConsoleChat as Record<string, unknown>).session_id || ""
        : "",
    ).trim();
    const canonicalTriggerMessageId = String(
      canonicalConsoleChat && typeof canonicalConsoleChat === "object" && !Array.isArray(canonicalConsoleChat)
        ? (canonicalConsoleChat as Record<string, unknown>).trigger_message_id || ""
        : "",
    ).trim();
    const canonicalRunId = String(
      canonicalConsoleChat && typeof canonicalConsoleChat === "object" && !Array.isArray(canonicalConsoleChat)
        ? (canonicalConsoleChat as Record<string, unknown>).run_id || ""
        : "",
    ).trim();
    const canonicalQueuedAt = String(
      canonicalConsoleChat && typeof canonicalConsoleChat === "object" && !Array.isArray(canonicalConsoleChat)
        ? (canonicalConsoleChat as Record<string, unknown>).queued_at || ""
        : "",
    ).trim();
    const canonicalStatus = String(canonicalTask.status || "").toUpperCase();

    const sameDispatchFingerprint =
      canonicalDispatchMode === "console_async_worker"
      && canonicalSessionId === sessionId
      && canonicalTriggerMessageId === triggerMessageId;

    if (sameDispatchFingerprint && DEDUP_STATUSES.has(canonicalStatus)) {
      return {
        runId: canonicalRunId || canonicalTask.id,
        taskId: canonicalTask.id,
        accepted: true,
        queuedAt: canonicalQueuedAt || String(canonicalTask.createdAt || canonicalTask.updatedAt || queuedAt),
      };
    }

    taskId = randomUUID();
  }

  try {
    await executeAppSyncGraphql(CREATE_TASK_MUTATION, {
      input: {
        id: taskId,
        accountId,
        type: "Procedure Run",
        status: "PENDING",
        // Console runs are already dispatched by SQS enqueue in this resolver.
        // Mark as DISPATCHED so generic task dispatchers do not execute them again.
        dispatchStatus: "DISPATCHED",
        target: `procedure/run/${procedureId}`,
        command: `procedure run ${procedureId}`,
        description: `Console async run ${runId}`,
        metadata: JSON.stringify(metadata),
        createdAt: queuedAt,
        updatedAt: queuedAt,
      },
    });
  } catch (error) {
    const existingAfterCreateFailure = await findExistingConsoleRun(accountId, procedureId, sessionId, triggerMessageId);
    if (existingAfterCreateFailure) {
      return {
        runId: existingAfterCreateFailure.runId,
        taskId: existingAfterCreateFailure.taskId,
        accepted: true,
        queuedAt: existingAfterCreateFailure.queuedAt,
      };
    }
    throw error;
  }

  const sqsClient = new SQSClient({ region: resolveAwsRegion() });
  try {
    await sqsClient.send(
      new SendMessageCommand({
        QueueUrl: queueUrl,
        MessageBody: JSON.stringify({
          runId,
          taskId,
          accountId,
          sessionId,
          procedureId,
          triggerMessageId,
          queuedAt,
          apiUrl: apiUrlForWorker,
          apiKey: apiKeyForWorker,
          instrumentation: clientInstrumentation,
        }),
      }),
    );
  } catch (error) {
    const failureAt = toIsoNow();
    await executeAppSyncGraphql(UPDATE_TASK_MUTATION, {
      input: {
        id: taskId,
        status: "FAILED",
        errorMessage: "Failed to enqueue console run worker job",
        errorDetails: JSON.stringify({
          message: error instanceof Error ? error.message : String(error),
        }),
        updatedAt: failureAt,
      },
    });
    throw error;
  }

  return {
    runId,
    taskId,
    accepted: true,
    queuedAt,
  };
};
