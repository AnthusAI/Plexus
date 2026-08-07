import { GetItemCommand, DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { Sha256 } from '@aws-crypto/sha256-js';
import { defaultProvider } from '@aws-sdk/credential-provider-node';
import { SignatureV4 } from '@aws-sdk/signature-v4';
import { HttpRequest } from '@aws-sdk/protocol-http';
import { createHash, randomUUID } from 'crypto';
import fetch, { Request } from 'node-fetch';

const dynamo = new DynamoDBClient({});
const NAMESPACE = 'command.submit:v1';

type Identity = { claims?: Record<string, unknown> };
type Event = {
  arguments: { accountId: string; action: string; arguments: unknown; idempotencyKey?: string };
  identity?: Identity;
};

function required(value: unknown, field: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${field} is required`);
  return value.trim();
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonical(item)}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

function authenticatedPrincipal(identity: Identity | undefined) {
  const claims = identity?.claims || {};
  return required(claims.sub ?? claims.username, 'authenticated principal identity');
}

function command(action: string, raw: unknown): { type: string; target: string; argv: string[] } {
  if (typeof raw === 'string') {
    try { raw = JSON.parse(raw); } catch { throw new Error('arguments must be valid JSON'); }
  }
  const args = raw && typeof raw === 'object' ? raw as Record<string, unknown> : {};
  const string = (name: string) => required(args[name], name);
  const optionalString = (name: string) => args[name] === undefined ? undefined : string(name);
  const rejectUnknown = (allowed: string[]) => {
    const unknown = Object.keys(args).filter((key) => !allowed.includes(key));
    if (unknown.length) throw new Error(`unsupported arguments: ${unknown.sort().join(', ')}`);
  };
  const integer = (name: string, minimum: number, maximum: number) => {
    const value = args[name];
    if (!Number.isInteger(value) || (value as number) < minimum || (value as number) > maximum) {
      throw new Error(`${name} must be an integer between ${minimum} and ${maximum}`);
    }
    return value as number;
  };
  const samples = args.numberOfSamples;
  const actionMap: Record<string, string> = {
    'evaluation.accuracy': 'accuracy',
  };
  const kind = actionMap[action];
  if (kind) {
    rejectUnknown(['scorecardName', 'scoreName', 'numberOfSamples', 'loadFresh', 'versionId']);
    const sampleCount = integer('numberOfSamples', 1, 10000);
    const argv = ['evaluate', kind, '--number-of-samples', String(sampleCount), '--scorecard', string('scorecardName'), '--score', string('scoreName')];
    if (args.loadFresh === true) argv.push('--fresh');
    if (optionalString('versionId')) argv.push('--version', optionalString('versionId')!);
    return { type: 'Evaluation', target: 'evaluation', argv };
  }
  if (action === 'evaluation.feedback') {
    rejectUnknown(['scorecardName', 'scoreName', 'days', 'versionId']);
    const argv = ['evaluate', 'feedback', '--scorecard', string('scorecardName'), '--score', string('scoreName')];
    if (args.days !== undefined) argv.push('--days', String(integer('days', 1, 3650)));
    if (optionalString('versionId')) argv.push('--version', optionalString('versionId')!);
    return { type: 'Feedback Evaluation', target: 'evaluation', argv };
  }
  if (action === 'prediction.run') {
    rejectUnknown(['scorecardName', 'scoreName', 'itemId', 'versionId']);
    const argv = ['predict', '--scorecard', string('scorecardName'), '--score', string('scoreName'), '--item', string('itemId'), '--format', 'json'];
    if (optionalString('versionId')) argv.push('--version', optionalString('versionId')!);
    return { type: 'Prediction Test', target: 'prediction', argv };
  }
  if (action === 'report.run') {
    rejectUnknown(['configurationId', 'parameters']);
    const argv = ['report', 'run', '--config', string('configurationId')];
    const parameters = args.parameters;
    if (parameters !== undefined) {
      if (!parameters || typeof parameters !== 'object' || Array.isArray(parameters)) throw new Error('parameters must be an object');
      for (const [key, value] of Object.entries(parameters as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b))) {
        if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(key) || !['string', 'number', 'boolean'].includes(typeof value)) throw new Error('report parameters must be named scalar values');
        argv.push(`--param-${key}=${String(value)}`);
      }
    }
    return { type: 'Report', target: 'report', argv };
  }
  if (action === 'procedure.run') {
    rejectUnknown(['procedureId', 'parameters']);
    const procedureId = string('procedureId');
    const argv = ['procedure', 'run', procedureId, '--output', 'json'];
    const parameters = args.parameters;
    if (parameters !== undefined) {
      if (!parameters || typeof parameters !== 'object' || Array.isArray(parameters)) throw new Error('procedure parameters must be an object');
      for (const [key, value] of Object.entries(parameters as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b))) {
        if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(key) || value === null || value === undefined) throw new Error('procedure parameters must have valid names and values');
        const encoded = typeof value === 'string' ? value : JSON.stringify(value);
        if (!encoded) throw new Error('procedure parameters must be JSON-serializable');
        argv.push('--set', `${key}=${encoded}`);
      }
    }
    return { type: 'Procedure', target: `procedure/run/${procedureId}`, argv };
  }
  if (action === 'feedback.report') {
    rejectUnknown(['report', 'scorecardId', 'scoreId', 'days', 'startDate', 'endDate', 'bucketType', 'timezone', 'weekStart']);
    const report = string('report');
    if (!['recent', 'alignment', 'timeline', 'volume', 'acceptance-rate', 'contradictions', 'acceptance-rate-timeline', 'overview'].includes(report)) throw new Error('unsupported feedback report');
    const argv = ['feedback', 'report', report, '--scorecard', string('scorecardId')];
    const scoreId = optionalString('scoreId');
    if (['contradictions', 'acceptance-rate-timeline', 'overview'].includes(report) && !scoreId) throw new Error(`${report} requires scoreId`);
    if (scoreId) argv.push('--score', scoreId);
    if (args.days !== undefined) argv.push('--days', String(integer('days', 1, 3650)));
    else if (optionalString('startDate') && optionalString('endDate')) argv.push('--start-date', optionalString('startDate')!, '--end-date', optionalString('endDate')!);
    else argv.push('--days', '90');
    if (['timeline', 'volume', 'overview'].includes(report)) {
      const bucketType = string('bucketType');
      if (!['calendar_week', 'calendar_month'].includes(bucketType)) throw new Error('invalid feedback report bucketType');
      argv.push('--bucket-type', bucketType, '--timezone', string('timezone'));
      const weekStart = optionalString('weekStart') || 'monday';
      if (!['monday', 'sunday'].includes(weekStart)) throw new Error('invalid feedback report weekStart');
      argv.push('--week-start', weekStart);
    } else if (report === 'acceptance-rate-timeline') {
      const bucketType = string('bucketType');
      if (!['trailing_7d', 'trailing_30d'].includes(bucketType)) throw new Error('invalid feedback report bucketType');
      argv.push('--bucket-type', bucketType);
    } else if (report === 'acceptance-rate') argv.push('--max-items', '200');
    return { type: 'Feedback Report', target: 'report', argv };
  }
  throw new Error('unsupported command action');
}

function bindTaskIdentity(action: string, argv: string[], taskId: string): string[] {
  if (action === 'procedure.run' || action === 'feedback.report') return argv;
  if (action === 'report.run') return [...argv.slice(0, 4), '--task-id', taskId, ...argv.slice(4)];
  return [...argv, '--task-id', taskId];
}

async function graphql(query: string, variables: Record<string, unknown>) {
  const endpointValue = required(process.env.PLEXUS_API_URL, 'PLEXUS_API_URL');
  const endpoint = new URL(endpointValue);
  const signed = await new SignatureV4({ credentials: defaultProvider(), region: required(process.env.AWS_REGION, 'AWS_REGION'), service: 'appsync', sha256: Sha256 }).sign(new HttpRequest({ method: 'POST', hostname: endpoint.host, path: endpoint.pathname, headers: { 'content-type': 'application/json', host: endpoint.host }, body: JSON.stringify({ query, variables }) }));
  const response = await fetch(new Request(endpointValue, signed));
  const payload = await response.json() as { data?: Record<string, unknown>; errors?: { message?: string }[] };
  if (!response.ok || payload.errors?.length) throw new Error(payload.errors?.[0]?.message || 'AppSync Task mutation failed');
  return payload.data || {};
}

export const handler = async (event: Event) => {
  const accountId = required(event.arguments.accountId, 'accountId');
  const submittedBy = authenticatedPrincipal(event.identity);
  const action = required(event.arguments.action, 'action');
  const builtCommand = command(action, event.arguments.arguments);
  const idempotencyKey = event.arguments.idempotencyKey
    ? required(event.arguments.idempotencyKey, 'idempotencyKey')
    : randomUUID();
  const id = `cmd_${createHash('sha256').update([accountId, submittedBy, NAMESPACE, idempotencyKey].join('\x1f')).digest('hex')}`;
  const argv = bindTaskIdentity(action, builtCommand.argv, id);
  const { type, target } = builtCommand;
  const payload = { argv, task_id: id };
  const digest = createHash('sha256').update(canonical({ payload, target }), 'utf8').digest('hex');
  const now = new Date().toISOString();
  const accountTableName = required(process.env.ACCOUNT_TABLE_NAME, 'ACCOUNT_TABLE_NAME');
  const account = await dynamo.send(new GetItemCommand({ TableName: accountTableName, Key: { id: { S: accountId } }, ConsistentRead: true }));
  if (!account.Item) throw new Error('selected account was not found');
  const input = { id, accountId, type, status: 'PENDING', target, command: argv.join(' '), dispatchStatus: 'READY', submittedBy, idempotencyNamespace: NAMESPACE, idempotencyKey, idempotencyDigest: digest, digestAlgorithm: 'sha256', digestCanonicalizationVersion: 1, commandPayload: payload, lifecycleStatus: 'ANNOUNCED', fencingToken: 0, createdAt: now, updatedAt: now };
  let persistedTask: Record<string, unknown> = input;
  try {
    const created = await graphql('mutation CreateTask($input: CreateTaskInput!, $condition: ModelTaskConditionInput) { createTask(input: $input, condition: $condition) { id accountId type status target command dispatchStatus lifecycleStatus commandPayload createdAt updatedAt } }', { input, condition: { id: { attributeExists: false } } });
    if (created.createTask && typeof created.createTask === 'object') persistedTask = { ...input, ...created.createTask as Record<string, unknown>, id };
  } catch (error: unknown) {
    if (!String(error).toLowerCase().includes('conditional')) throw error;
    const existing = await graphql('query GetTask($id: ID!) { getTask(id: $id) { id accountId type status target command dispatchStatus lifecycleStatus commandPayload createdAt updatedAt idempotencyDigest } }', { id }) as { getTask?: Record<string, unknown> };
    if (!existing.getTask || existing.getTask.accountId !== accountId || existing.getTask.target !== target || existing.getTask.idempotencyDigest !== digest) {
      throw new Error('idempotency key conflicts with a different command');
    }
    persistedTask = { ...input, ...existing.getTask, id };
  }
  return { taskId: id, ...persistedTask };
};
