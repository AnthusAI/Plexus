import { randomUUID } from "crypto";
import { Sha256 } from "@aws-crypto/sha256-js";
import { SQSClient, SendMessageCommand } from "@aws-sdk/client-sqs";
import { defaultProvider } from "@aws-sdk/credential-provider-node";
import { HttpRequest } from "@aws-sdk/protocol-http";
import { SignatureV4 } from "@aws-sdk/signature-v4";

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

function resolveGraphqlEndpoint(): string {
  return (
    process.env.PLEXUS_API_URL ||
    process.env.API_GRAPHQLAPIENDPOINTOUTPUT ||
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

type GraphqlEnvelope<TData> = {
  data?: TData;
  errors?: Array<{ message?: string }>;
};

async function executeAppSyncGraphql<TData>(
  query: string,
  variables: Record<string, unknown>,
): Promise<TData> {
  const endpoint = resolveGraphqlEndpoint();
  if (!endpoint) {
    throw new Error("PLEXUS_API_URL is not configured for startConsoleRun resolver");
  }
  const region = resolveAwsRegion();
  const endpointUrl = new URL(endpoint);
  const signer = new SignatureV4({
    credentials: defaultProvider(),
    region,
    service: "appsync",
    sha256: Sha256,
  });

  const request = new HttpRequest({
    method: "POST",
    protocol: endpointUrl.protocol,
    hostname: endpointUrl.host,
    path: endpointUrl.pathname,
    headers: {
      "content-type": "application/json",
      host: endpointUrl.host,
    },
    body: JSON.stringify({ query, variables }),
  });

  const signed = await signer.sign(request);
  const response = await fetch(endpoint, {
    method: "POST",
    headers: signed.headers as Record<string, string>,
    body: typeof signed.body === "string" ? signed.body : JSON.stringify(signed.body),
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

export const handler = async (event: any) => {
  const sessionId = event.arguments.sessionId?.trim();
  const procedureId = event.arguments.procedureId?.trim();
  const triggerMessageId = event.arguments.triggerMessageId?.trim();
  const queueUrl = (process.env.CONSOLE_RUN_QUEUE_URL || "").trim();

  if (!isValidId(sessionId)) {
    throw new Error("startConsoleRun requires a valid sessionId");
  }
  if (!isValidProcedureId(procedureId)) {
    throw new Error("startConsoleRun requires a valid procedureId");
  }
  if (!isValidId(triggerMessageId)) {
    throw new Error("startConsoleRun requires a valid triggerMessageId");
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

  const runId = randomUUID();
  const taskId = randomUUID();
  const queuedAt = toIsoNow();
  const clientInstrumentation = normalizeInstrumentation(event.arguments.clientInstrumentation);
  const metadata = {
    dispatch_mode: queueUrl ? "console_async_worker" : "task_dispatcher",
    console_chat: {
      session_id: sessionId,
      trigger_message_id: triggerMessageId,
      queued_at: queuedAt,
      run_id: runId,
      instrumentation: {
        ...clientInstrumentation,
        queue_enqueued_at: queuedAt,
      },
    },
  };

  await executeAppSyncGraphql(CREATE_TASK_MUTATION, {
    input: {
      id: taskId,
      accountId,
      type: "Procedure Run",
      status: "PENDING",
      dispatchStatus: "PENDING",
      target: `procedure/run/${procedureId}`,
      command: `procedure run ${procedureId}`,
      description: `Console async run ${runId}`,
      metadata: JSON.stringify(metadata),
      createdAt: queuedAt,
      updatedAt: queuedAt,
    },
  });

  if (queueUrl) {
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
  }

  return {
    runId,
    taskId,
    accepted: true,
    queuedAt,
  };
};
