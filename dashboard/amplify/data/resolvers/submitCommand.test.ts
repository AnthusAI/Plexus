jest.mock('@aws-sdk/client-dynamodb', () => ({
  DynamoDBClient: jest.fn(() => ({ send: jest.fn() })),
  PutItemCommand: jest.fn((input) => ({ input })),
  GetItemCommand: jest.fn((input) => ({ input })),
}));
jest.mock('node-fetch', () => ({ __esModule: true, default: jest.fn(), Request: jest.fn((_url, request) => request) }));
jest.mock('@aws-sdk/credential-provider-node', () => ({ defaultProvider: jest.fn(() => jest.fn()) }));
jest.mock('@aws-sdk/signature-v4', () => ({ SignatureV4: jest.fn(() => ({ sign: jest.fn(async (request) => request) })) }));

import { handler } from './submitCommand';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import fetch from 'node-fetch';

const mockSend = (DynamoDBClient as unknown as jest.Mock).mock.results[0].value.send as jest.Mock;
const mockFetch = fetch as unknown as jest.Mock;
const putInput = () => mockSend.mock.calls[1][0].input;

const event = (overrides: Record<string, unknown> = {}) => ({
  arguments: { accountId: 'account-1', action: 'evaluation.accuracy', arguments: { scorecardName: 'Card', scoreName: 'Score Name', numberOfSamples: 10, loadFresh: true }, idempotencyKey: 'stable-key', ...overrides },
  identity: { claims: { sub: 'user-1' } },
});

describe('submitCommand', () => {
  beforeEach(() => {
    process.env.TASK_TABLE_NAME = 'Task';
    process.env.ACCOUNT_TABLE_NAME = 'Account';
    process.env.PLEXUS_API_URL = 'https://example.appsync-api.us-east-1.amazonaws.com/graphql';
    process.env.AWS_REGION = 'us-east-1';
    mockSend.mockReset();
    mockFetch.mockReset();
  });

  it('uses AppSync identity and conditionally writes the typed command Task directly to DynamoDB', async () => {
    mockSend.mockResolvedValueOnce({ Item: { id: { S: 'account-1' } } });
    mockSend.mockResolvedValueOnce({});
    await expect(handler(event())).resolves.toMatchObject({ accountId: 'account-1', dispatchStatus: 'READY' });
    const put = putInput();
    expect(put.TableName).toBe('Task');
    expect(put.ConditionExpression).toBe('attribute_not_exists(id)');
    expect(put.Item.accountId).toEqual({ S: 'account-1' });
    const commandPayload = JSON.parse(put.Item.commandPayload.S);
    expect(commandPayload.argv).toEqual(['evaluate', 'accuracy', '--number-of-samples', '10', '--scorecard', 'Card', '--score', 'Score Name', '--fresh', '--task-id', put.Item.id.S]);
    expect(commandPayload.task_id).toBe(put.Item.id.S);
    expect(put.Item.idempotencyDigest.S).toMatch(/^[a-f0-9]{64}$/);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('verifies the persisted identity and digest on conditional replay', async () => {
    mockSend.mockResolvedValueOnce({ Item: { id: { S: 'account-1' } } });
    mockSend.mockRejectedValueOnce(Object.assign(new Error('conditional request failed'), { name: 'ConditionalCheckFailedException' }));
    mockSend.mockResolvedValueOnce({ Item: { accountId: { S: 'account-1' }, target: { S: 'evaluation' }, idempotencyDigest: { S: 'd' } } });
    // A collision must compare the persisted digest, not merely return an existing Task.
    await expect(handler(event())).rejects.toThrow('idempotency key conflicts');
  });

  it('returns the prior Task only when a conditional replay has the same identity and command digest', async () => {
    let idempotencyDigest = '';
    mockSend.mockImplementation((request) => {
      const input = request.input;
      if (input.TableName === 'Account') return { Item: { id: { S: 'account-1' } } };
      if (input.ConditionExpression) {
        idempotencyDigest = input.Item.idempotencyDigest.S;
        return Promise.reject(Object.assign(new Error('conditional request failed'), { name: 'ConditionalCheckFailedException' }));
      }
      return { Item: { id: input.Key.id, accountId: { S: 'account-1' }, target: { S: 'evaluation' }, idempotencyDigest: { S: idempotencyDigest }, status: { S: 'PENDING' } } };
    });

    await expect(handler(event())).resolves.toMatchObject({ accountId: 'account-1', target: 'evaluation', status: 'PENDING' });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('rejects unregistered actions and unknown selected accounts', async () => {
    await expect(handler(event({ action: 'shell.execute' }))).rejects.toThrow('unsupported command action');
    await expect(handler(event({ action: 'evaluation.consistency' }))).rejects.toThrow('unsupported command action');
    mockSend.mockResolvedValueOnce({});
    await expect(handler(event())).rejects.toThrow('selected account was not found');
  });

  it.each([
    ['evaluation.accuracy', { scorecardName: 'Card', scoreName: 'Score', numberOfSamples: 1, argv: ['shell'] }],
    ['evaluation.feedback', { scorecardName: 'Card', scoreName: 'Score', command: 'shell' }],
    ['prediction.run', { scorecardName: 'Card', scoreName: 'Score', itemId: 'item-1', arguments: ['shell'] }],
    ['report.run', { configurationId: 'report-1', command: 'shell' }],
    ['feedback.report', { report: 'recent', scorecardId: 'card-1', days: 7, argv: ['shell'] }],
  ])('%s rejects caller-supplied command material', async (action, arguments_) => {
    await expect(handler(event({ action, arguments: arguments_ }))).rejects.toThrow('unsupported arguments');
  });

  it('rejects missing AppSync identity and conflicting replay', async () => {
    await expect(handler({ ...event(), identity: undefined })).rejects.toThrow('authenticated principal identity');
  });

  it.each([
    ['evaluation.feedback', { scorecardName: 'Card', scoreName: 'Score', days: 7 }, ['evaluate', 'feedback', '--scorecard', 'Card', '--score', 'Score', '--days', '7']],
    ['prediction.run', { scorecardName: 'Card', scoreName: 'Score', itemId: 'item-1' }, ['predict', '--scorecard', 'Card', '--score', 'Score', '--item', 'item-1', '--format', 'json']],
    ['report.run', { configurationId: 'report-1', parameters: { days: 7 } }, ['report', 'run', '--config', 'report-1', '--param-days=7']],
    ['procedure.run', { procedureId: 'procedure-1', parameters: { max_iterations: 5, scorecard_ids: ['card-1', 'card-2'], selection: { window: { days: 14 } } } }, ['procedure', 'run', 'procedure-1', '--output', 'json', '--set', 'max_iterations=5', '--set', 'scorecard_ids=["card-1","card-2"]', '--set', 'selection={"window":{"days":14}}']],
    ['feedback.report', { report: 'timeline', scorecardId: 'card-1', days: 14, bucketType: 'calendar_week', timezone: 'UTC', weekStart: 'monday' }, ['feedback', 'report', 'timeline', '--scorecard', 'card-1', '--days', '14', '--bucket-type', 'calendar_week', '--timezone', 'UTC', '--week-start', 'monday']],
  ])('constructs %s argv only from its registered structured fields', async (action, arguments_, argv) => {
    mockSend.mockResolvedValueOnce({ Item: { id: { S: 'account-1' } } });
    mockSend.mockResolvedValueOnce({});
    await handler(event({ action, arguments: arguments_ }));
    const put = putInput();
    const taskId = put.Item.id.S;
    const expectedArgv = action === 'procedure.run' || action === 'feedback.report'
      ? argv
      : action === 'report.run'
        ? [...argv.slice(0, 4), '--task-id', taskId, ...argv.slice(4)]
        : [...argv, '--task-id', taskId];
    expect(JSON.parse(put.Item.commandPayload.S)).toEqual({ argv: expectedArgv, task_id: taskId });
  });

  it.each([
    ['recent', ['feedback', 'report', 'recent', '--scorecard', 'card-1', '--days', '14']],
    ['alignment', ['feedback', 'report', 'alignment', '--scorecard', 'card-1', '--days', '14']],
    ['timeline', ['feedback', 'report', 'timeline', '--scorecard', 'card-1', '--days', '14', '--bucket-type', 'calendar_week', '--timezone', 'UTC', '--week-start', 'monday']],
    ['volume', ['feedback', 'report', 'volume', '--scorecard', 'card-1', '--days', '14', '--bucket-type', 'calendar_week', '--timezone', 'UTC', '--week-start', 'monday']],
    ['acceptance-rate', ['feedback', 'report', 'acceptance-rate', '--scorecard', 'card-1', '--days', '14', '--max-items', '200']],
    ['contradictions', ['feedback', 'report', 'contradictions', '--scorecard', 'card-1', '--score', 'score-1', '--days', '14']],
    ['acceptance-rate-timeline', ['feedback', 'report', 'acceptance-rate-timeline', '--scorecard', 'card-1', '--score', 'score-1', '--days', '14', '--bucket-type', 'trailing_7d']],
    ['overview', ['feedback', 'report', 'overview', '--scorecard', 'card-1', '--score', 'score-1', '--days', '14', '--bucket-type', 'calendar_week', '--timezone', 'UTC', '--week-start', 'monday']],
  ])('constructs parser-compatible argv for feedback report %s', async (report, argv) => {
    mockSend.mockResolvedValueOnce({ Item: { id: { S: 'account-1' } } });
    mockSend.mockResolvedValueOnce({});
    const arguments_: Record<string, unknown> = { report, scorecardId: 'card-1', days: 14 };
    if (['contradictions', 'acceptance-rate-timeline', 'overview'].includes(report)) arguments_.scoreId = 'score-1';
    if (['timeline', 'volume', 'overview'].includes(report)) Object.assign(arguments_, { bucketType: 'calendar_week', timezone: 'UTC', weekStart: 'monday' });
    if (report === 'acceptance-rate-timeline') arguments_.bucketType = 'trailing_7d';
    await handler(event({ action: 'feedback.report', arguments: arguments_ }));
    const put = putInput();
    expect(JSON.parse(put.Item.commandPayload.S)).toEqual({ argv, task_id: put.Item.id.S });
  });

  it.each([
    { procedureId: 'procedure-1', command: 'procedure run procedure-1' },
    { procedureId: 'procedure-1', argv: ['procedure', 'run', 'other'] },
    { procedureId: 'procedure-1', parameters: [] },
    { procedureId: 'procedure-1', parameters: { bad: null } },
  ])('rejects caller command material and malformed procedure input: %p', async (arguments_) => {
    await expect(handler(event({ action: 'procedure.run', arguments: arguments_ }))).rejects.toThrow();
  });

  it.each(['contradictions', 'acceptance-rate-timeline', 'overview'])('%s rejects missing scoreId', async (report) => {
    await expect(handler(event({ action: 'feedback.report', arguments: { report, scorecardId: 'card-1', days: 14 } }))).rejects.toThrow('requires scoreId');
  });
});
