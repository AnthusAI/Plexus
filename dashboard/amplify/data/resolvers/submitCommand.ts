import { GetItemCommand, PutItemCommand, DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { marshall, unmarshall } from '@aws-sdk/util-dynamodb';
import { createHash, randomUUID } from 'crypto';
import { isRegisteredCommandAction, parseCommandArguments, rejectUnsupportedArguments } from '../../../lib/command-contract';

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
  if (!isRegisteredCommandAction(action)) throw new Error('unsupported command action');
  const args = parseCommandArguments(raw);
  rejectUnsupportedArguments(action, args);
  const string = (name: string) => required(args[name], name);
  const optionalString = (name: string) => args[name] === undefined ? undefined : string(name);
  const integer = (name: string, minimum: number, maximum: number) => {
    const value = args[name];
    if (!Number.isInteger(value) || (value as number) < minimum || (value as number) > maximum) {
      throw new Error(`${name} must be an integer between ${minimum} and ${maximum}`);
    }
    return value as number;
  };
  const actionMap: Record<string, string> = {
    'evaluation.accuracy': 'accuracy',
  };
  const kind = actionMap[action];
  if (kind) {
    const sampleCount = integer('numberOfSamples', 1, 10000);
    const argv = ['evaluate', kind, '--number-of-samples', String(sampleCount), '--scorecard', string('scorecardName'), '--score', string('scoreName')];
    if (args.loadFresh === true) argv.push('--fresh');
    if (optionalString('versionId')) argv.push('--version', optionalString('versionId')!);
    return { type: 'Evaluation', target: 'evaluation', argv };
  }
  if (action === 'evaluation.feedback') {
    const argv = ['evaluate', 'feedback', '--scorecard', string('scorecardName'), '--score', string('scoreName')];
    if (args.days !== undefined) argv.push('--days', String(integer('days', 1, 3650)));
    if (optionalString('versionId')) argv.push('--version', optionalString('versionId')!);
    return { type: 'Feedback Evaluation', target: 'evaluation', argv };
  }
  if (action === 'prediction.run') {
    const argv = ['predict', '--scorecard', string('scorecardName'), '--score', string('scoreName'), '--item', string('itemId'), '--format', 'json'];
    if (optionalString('versionId')) argv.push('--version', optionalString('versionId')!);
    return { type: 'Prediction Test', target: 'prediction', argv };
  }
  if (action === 'report.run') {
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
  throw new Error(`unsupported command action: ${action}`);
}

function bindTaskIdentity(action: string, argv: string[], taskId: string): string[] {
  if (action === 'procedure.run' || action === 'feedback.report') return argv;
  if (action === 'report.run') return [...argv.slice(0, 4), '--task-id', taskId, ...argv.slice(4)];
  return [...argv, '--task-id', taskId];
}

function isConditionalFailure(error: unknown): boolean {
  return (error as { name?: unknown })?.name === 'ConditionalCheckFailedException'
    || String(error).toLowerCase().includes('conditional');
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
  const taskTableName = required(process.env.TASK_TABLE_NAME, 'TASK_TABLE_NAME');
  const account = await dynamo.send(new GetItemCommand({ TableName: accountTableName, Key: { id: { S: accountId } }, ConsistentRead: true }));
  if (!account.Item) throw new Error('selected account was not found');
  const input = { id, accountId, type, status: 'PENDING', target, command: argv.join(' '), dispatchStatus: 'READY', submittedBy, idempotencyNamespace: NAMESPACE, idempotencyKey, idempotencyDigest: digest, digestAlgorithm: 'sha256', digestCanonicalizationVersion: 1, commandPayload: JSON.stringify(payload), lifecycleStatus: 'ANNOUNCED', fencingToken: 0, createdAt: now, updatedAt: now };
  let persistedTask: Record<string, unknown> = input;
  try {
    await dynamo.send(new PutItemCommand({
      TableName: taskTableName,
      Item: marshall(input),
      ConditionExpression: 'attribute_not_exists(id)',
    }));
  } catch (error: unknown) {
    if (!isConditionalFailure(error)) throw error;
    const existing = await dynamo.send(new GetItemCommand({
      TableName: taskTableName,
      Key: { id: { S: id } },
      ConsistentRead: true,
    }));
    const existingTask = existing.Item ? unmarshall(existing.Item) : undefined;
    if (!existingTask || existingTask.accountId !== accountId || existingTask.target !== target || existingTask.idempotencyDigest !== digest) {
      throw new Error('idempotency key conflicts with a different command');
    }
    persistedTask = { ...input, ...existingTask, id };
  }
  return { taskId: id, ...persistedTask };
};
