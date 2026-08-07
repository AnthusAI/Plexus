jest.mock('@aws-sdk/credential-provider-node', () => ({ defaultProvider: jest.fn(() => jest.fn()) }));
jest.mock('@aws-sdk/signature-v4', () => ({ SignatureV4: jest.fn(() => ({ sign: jest.fn(async (request) => request) })) }));
jest.mock('node-fetch', () => ({ __esModule: true, default: jest.fn(), Request: jest.fn((_url, request) => request) }));

import fetch from 'node-fetch';
import { handler } from './cancelCommand';
const mockFetch = fetch as unknown as jest.Mock;
const event = { arguments: { accountId: 'account-1', taskId: 'task-1' }, identity: { claims: { sub: 'user-1' } } };
const reply = (data: unknown, errors?: unknown[]) => ({ ok: true, json: async () => ({ data, errors }) });

describe('cancelCommand', () => {
  beforeEach(() => { process.env.PLEXUS_API_URL = 'https://example.appsync-api.us-east-1.amazonaws.com/graphql'; process.env.AWS_REGION = 'us-east-1'; mockFetch.mockReset(); });
  it.each(['ANNOUNCED', 'RUNNING'])('conditionally requests cancellation from %s', async (lifecycleStatus) => {
    mockFetch.mockResolvedValueOnce(reply({ getTask: { id: 'task-1', accountId: 'account-1', lifecycleStatus, dispatchStatus: 'READY' } })).mockResolvedValueOnce(reply({ updateTask: { id: 'task-1', dispatchStatus: 'READY' } }));
    await expect(handler(event)).resolves.toMatchObject({ taskId: 'task-1' });
    expect(JSON.parse(mockFetch.mock.calls[1][0].body).variables.condition.lifecycleStatus).toEqual({ eq: lifecycleStatus });
  });
  it('is idempotent for requested and terminal states', async () => {
    for (const lifecycleStatus of ['CANCEL_REQUESTED', 'SUCCEEDED', 'FAILED', 'CANCELLED']) {
      mockFetch.mockResolvedValueOnce(reply({ getTask: { id: 'task-1', accountId: 'account-1', lifecycleStatus, dispatchStatus: 'READY' } }));
      await handler(event);
    }
    expect(mockFetch).toHaveBeenCalledTimes(4);
  });
  it('rejects a cross-account request and preserves a completion race', async () => {
    mockFetch.mockResolvedValueOnce(reply({ getTask: { id: 'task-1', accountId: 'other', lifecycleStatus: 'RUNNING' } }));
    await expect(handler(event)).rejects.toThrow('not found');
    mockFetch.mockResolvedValueOnce(reply({ getTask: { id: 'task-1', accountId: 'account-1', lifecycleStatus: 'RUNNING' } })).mockResolvedValueOnce(reply({}, [{ message: 'Conditional request failed' }])).mockResolvedValueOnce(reply({ getTask: { accountId: 'account-1', dispatchStatus: 'COMPLETED' } }));
    await expect(handler(event)).resolves.toMatchObject({ dispatchStatus: 'COMPLETED' });
  });
});
