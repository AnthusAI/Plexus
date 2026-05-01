import { fetchAuthSession } from 'aws-amplify/auth'
import {
  CloudWatchLogsClient,
  GetLogEventsCommand,
  GetLogEventsCommandOutput,
} from '@aws-sdk/client-cloudwatch-logs'

function resolveAwsRegion(): string {
  const regionOverride = process.env.NEXT_PUBLIC_PLEXUS_API_REGION?.trim()
  if (regionOverride) return regionOverride

  try {
    const outputs = require('../amplify_outputs.json')
    return outputs?.data?.aws_region || outputs?.aws_region || 'us-west-2'
  } catch {
    return 'us-west-2'
  }
}

async function getClient(): Promise<CloudWatchLogsClient> {
  const session = await fetchAuthSession()
  return new CloudWatchLogsClient({
    region: resolveAwsRegion(),
    credentials: session.credentials,
  })
}

export interface LogPage {
  events: Array<{ timestamp: number; message: string }>
  nextForwardToken: string | undefined
  nextBackwardToken: string | undefined
}

async function fetchLogStream(
  logGroup: string,
  streamName: string,
  nextToken?: string,
  startFromHead = true,
): Promise<LogPage> {
  const cw = await getClient()
  const response: GetLogEventsCommandOutput = await cw.send(
    new GetLogEventsCommand({
      logGroupName: logGroup,
      logStreamName: streamName,
      nextToken,
      startFromHead,
      limit: 100,
    }),
  )
  return {
    events: (response.events ?? []).map((e) => ({
      timestamp: e.timestamp ?? 0,
      message: e.message ?? '',
    })),
    nextForwardToken: response.nextForwardToken,
    nextBackwardToken: response.nextBackwardToken,
  }
}

/**
 * Fetch a page of run log events for a procedure invocation.
 *
 * The stream name is: {procedureId}/run/{invocationRunId}
 * Since invocationRunId is not stored directly, callers pass the full stream
 * name or use fetchAllRunStreams to list available streams.
 */
export async function fetchProcedureRunLogs(
  logGroup: string,
  streamName: string,
  nextToken?: string,
): Promise<LogPage> {
  return fetchLogStream(logGroup, streamName, nextToken, true)
}

/**
 * Fetch a page of LLM context log events for a procedure invocation.
 *
 * The stream name is: {procedureId}/llm-context/{invocationRunId}
 */
export async function fetchProcedureLlmContextLogs(
  logGroup: string,
  streamName: string,
  nextToken?: string,
): Promise<LogPage> {
  return fetchLogStream(logGroup, streamName, nextToken, true)
}
