import { Sha256 } from '@aws-crypto/sha256-js';
import { defaultProvider } from '@aws-sdk/credential-provider-node';
import { SignatureV4 } from '@aws-sdk/signature-v4';
import { HttpRequest } from '@aws-sdk/protocol-http';
import fetch, { Request } from 'node-fetch';

type Event = { arguments: { accountId: string; taskId: string }; identity?: { claims?: Record<string, unknown> } };
const required = (value: unknown, name: string) => {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${name} is required`);
  return value.trim();
};
async function graphql(query: string, variables: Record<string, unknown>) {
  const url = required(process.env.PLEXUS_API_URL, 'PLEXUS_API_URL');
  const endpoint = new URL(url);
  const request = await new SignatureV4({ credentials: defaultProvider(), region: required(process.env.AWS_REGION, 'AWS_REGION'), service: 'appsync', sha256: Sha256 }).sign(new HttpRequest({ method: 'POST', hostname: endpoint.host, path: endpoint.pathname, headers: { host: endpoint.host, 'content-type': 'application/json' }, body: JSON.stringify({ query, variables }) }));
  const response = await fetch(new Request(url, request));
  const payload = await response.json() as { data?: Record<string, unknown>; errors?: { message?: string }[] };
  if (!response.ok || payload.errors?.length) throw new Error(payload.errors?.[0]?.message || 'AppSync Task mutation failed');
  return payload.data || {};
}
export const handler = async (event: Event) => {
  required(event.identity?.claims?.sub ?? event.identity?.claims?.username, 'authenticated principal identity');
  const accountId = required(event.arguments.accountId, 'accountId');
  const taskId = required(event.arguments.taskId, 'taskId');
  const task = await graphql('query GetTask($id: ID!) { getTask(id: $id) { id accountId lifecycleStatus dispatchStatus } }', { id: taskId }) as { getTask?: { id: string; accountId: string; lifecycleStatus?: string; dispatchStatus?: string } };
  if (!task.getTask || task.getTask.accountId !== accountId) throw new Error('command Task was not found');
  if (['CANCEL_REQUESTED', 'SUCCEEDED', 'FAILED', 'CANCELLED'].includes(task.getTask.lifecycleStatus || '')) return { taskId, accountId, dispatchStatus: task.getTask.dispatchStatus || '' };
  try {
    const updated = await graphql('mutation UpdateTask($input: UpdateTaskInput!, $condition: ModelTaskConditionInput) { updateTask(input: $input, condition: $condition) { id dispatchStatus } }', { input: { id: taskId, lifecycleStatus: 'CANCEL_REQUESTED', cancellationRequestedAt: new Date().toISOString() }, condition: { accountId: { eq: accountId }, lifecycleStatus: { eq: task.getTask.lifecycleStatus } } }) as { updateTask?: { dispatchStatus?: string } };
    return { taskId, accountId, dispatchStatus: updated.updateTask?.dispatchStatus || '' };
  } catch (error) {
    if (!String(error).toLowerCase().includes('conditional')) throw error;
    const reloaded = await graphql('query GetTask($id: ID!) { getTask(id: $id) { accountId dispatchStatus } }', { id: taskId }) as { getTask?: { accountId?: string; dispatchStatus?: string } };
    if (!reloaded.getTask || reloaded.getTask.accountId !== accountId) throw new Error('command Task was not found');
    return { taskId, accountId, dispatchStatus: reloaded.getTask.dispatchStatus || '' };
  }
};
