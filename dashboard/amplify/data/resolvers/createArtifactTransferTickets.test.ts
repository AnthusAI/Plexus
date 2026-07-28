import { handler } from './createArtifactTransferTickets';

jest.mock('@aws-sdk/client-dynamodb', () => ({
  DynamoDBClient: jest.fn(() => ({ send: jest.fn() })),
  GetItemCommand: jest.fn((input) => input),
}));

jest.mock('@aws-sdk/client-s3', () => ({
  GetObjectCommand: jest.fn((input) => input),
  PutObjectCommand: jest.fn((input) => input),
  S3Client: jest.fn(),
}));

jest.mock('@aws-sdk/s3-request-presigner', () => ({ getSignedUrl: jest.fn() }), { virtual: true });

const mockGetSignedUrl = jest.requireMock('@aws-sdk/s3-request-presigner').getSignedUrl as jest.Mock;
const dynamoSend = jest.requireMock('@aws-sdk/client-dynamodb').DynamoDBClient.mock.results[0].value.send as jest.Mock;
const mockGetItemCommand = jest.requireMock('@aws-sdk/client-dynamodb').GetItemCommand as jest.Mock;

const sha256 = 'a'.repeat(64);

const event = (requests: unknown[]) => ({
  arguments: { requests },
  identity: {
    claims: { sub: 'user-1', 'custom:account_id': 'account-1' },
  },
});

describe('createArtifactTransferTickets', () => {
  beforeEach(() => {
    jest.resetAllMocks();
    process.env.DATA_SET_TABLE_NAME = 'DataSet-table';
    process.env.DATA_SOURCES_BUCKET_NAME = 'data-sources-bucket';
    mockGetSignedUrl.mockResolvedValue('https://signed.example.test/ticket');
  });

  it('issues a five-minute write ticket with a server-derived dataset object key', async () => {
    dynamoSend.mockResolvedValue({
      Item: {
        id: { S: 'dataset-1' },
        accountId: { S: 'account-1' },
      },
    });

    const result = await handler(event([{
      operation: 'WRITE',
      resourceType: 'DATA_SET',
      resourceId: 'dataset-1',
      artifactType: 'DATASET_FILE',
      filename: 'training.csv',
      contentType: 'text/csv',
      sizeBytes: 42,
      sha256,
    }]) as any);

    expect(result).toEqual([{
      objectKey: 'datasets/account-1/dataset-1/training.csv',
      method: 'PUT',
      url: 'https://signed.example.test/ticket',
      requiredHeaders: {
        'content-type': 'text/csv',
        'content-length': '42',
        'x-amz-checksum-sha256': Buffer.from(sha256, 'hex').toString('base64'),
      },
      expiresAt: expect.any(String),
    }]);
    expect(new Date(result[0].expiresAt).getTime() - Date.now()).toBeLessThanOrEqual(5 * 60 * 1000);
    expect(new Date(result[0].expiresAt).getTime() - Date.now()).toBeGreaterThan(4 * 60 * 1000);
    expect(mockGetItemCommand).toHaveBeenCalledWith({
      TableName: 'DataSet-table',
      Key: { id: { S: 'dataset-1' } },
      ConsistentRead: true,
    });
  });

  it('issues a read ticket to an authenticated IAM workload', async () => {
    dynamoSend.mockResolvedValue({
      Item: {
        id: { S: 'dataset-1' },
        accountId: { S: 'account-1' },
      },
    });

    await expect(handler({
      arguments: { requests: [{
        operation: 'READ',
        resourceType: 'DATA_SET',
        resourceId: 'dataset-1',
        artifactType: 'DATASET_FILE',
        filename: 'training.csv',
        contentType: 'text/csv',
        sizeBytes: 42,
        sha256,
      }] },
      identity: { userArn: 'arn:aws:iam::123456789012:role/workload', accountId: '123456789012' },
    } as any)).resolves.toEqual([expect.objectContaining({
      objectKey: 'datasets/account-1/dataset-1/training.csv',
      method: 'GET',
      requiredHeaders: {},
    })]);
  });

  it('rejects a trusted account claim that does not match the resource account', async () => {
    dynamoSend.mockResolvedValue({
      Item: {
        id: { S: 'dataset-1' },
        accountId: { S: 'account-1' },
      },
    });

    await expect(handler({
      arguments: { requests: [{
        operation: 'READ', resourceType: 'DATA_SET', resourceId: 'dataset-1', artifactType: 'DATASET_FILE', filename: 'training.csv', contentType: 'text/csv', sizeBytes: 42, sha256,
      }] },
      identity: { claims: { sub: 'user-1', 'custom:account_id': 'account-2' } },
    } as any)).rejects.toThrow('Requested resource belongs to a different account');

    expect(mockGetSignedUrl).not.toHaveBeenCalled();
  });

  it('normalizes an uppercase SHA-256 checksum before issuing a write ticket', async () => {
    dynamoSend.mockResolvedValue({ Item: { id: { S: 'dataset-1' }, accountId: { S: 'account-1' } } });

    await expect(handler(event([{
      operation: 'WRITE', resourceType: 'DATA_SET', resourceId: 'dataset-1', artifactType: 'DATASET_FILE', filename: 'training.csv', contentType: 'text/csv', sizeBytes: 42, sha256: sha256.toUpperCase(),
    }]) as any)).resolves.toEqual([expect.objectContaining({
      requiredHeaders: expect.objectContaining({
        'x-amz-checksum-sha256': Buffer.from(sha256, 'hex').toString('base64'),
      }),
    })]);
  });

  it('preserves safe nested task artifact names while deriving the account-scoped key', async () => {
    process.env.TASK_TABLE_NAME = 'Task-table';
    process.env.TASK_ATTACHMENTS_BUCKET_NAME = 'task-attachments-bucket';
    dynamoSend.mockResolvedValue({ Item: { id: { S: 'task-1' }, accountId: { S: 'account-1' } } });

    await expect(handler(event([{
      operation: 'READ', resourceType: 'TASK', resourceId: 'task-1', artifactType: 'TASK_ATTACHMENT', filename: 'optimizer/manifest.json', contentType: 'application/json', sizeBytes: 42, sha256,
    }]) as any)).resolves.toEqual([expect.objectContaining({
      objectKey: 'tasks/task-1/optimizer/manifest.json',
      method: 'GET',
    })]);
  });

  it('preserves the legacy procedure dashboard-state key layout', async () => {
    process.env.PROCEDURE_TABLE_NAME = 'Procedure-table';
    process.env.REPORT_BLOCK_DETAILS_BUCKET_NAME = 'report-block-details-bucket';
    dynamoSend.mockResolvedValue({ Item: { id: { S: 'procedure-1' }, accountId: { S: 'account-1' } } });

    await expect(handler(event([{
      operation: 'READ', resourceType: 'PROCEDURE', resourceId: 'procedure-1', artifactType: 'PROCEDURE_DASHBOARD_STATE', filename: 'dashboard_state.json', contentType: 'application/json', sizeBytes: 42, sha256,
    }]) as any)).resolves.toEqual([expect.objectContaining({
      objectKey: 'reportblocks/procedures/procedure-1/dashboard_state.json',
      method: 'GET',
    })]);
  });

  it('preserves the existing procedure attachment key layout', async () => {
    process.env.PROCEDURE_TABLE_NAME = 'Procedure-table';
    process.env.REPORT_BLOCK_DETAILS_BUCKET_NAME = 'report-block-details-bucket';
    dynamoSend.mockResolvedValue({ Item: { id: { S: 'procedure-1' }, accountId: { S: 'account-1' } } });

    await expect(handler(event([{
      operation: 'READ', resourceType: 'PROCEDURE', resourceId: 'procedure-1', artifactType: 'PROCEDURE_ATTACHMENT', filename: 'definition.tac', contentType: 'text/plain', sizeBytes: 42, sha256,
    }]) as any)).resolves.toEqual([expect.objectContaining({
      objectKey: 'procedures/procedure-1/definition.tac',
    })]);
  });

  it('preserves the existing score-result attachment key layout', async () => {
    process.env.SCORE_RESULT_TABLE_NAME = 'ScoreResult-table';
    process.env.SCORE_RESULT_ATTACHMENTS_BUCKET_NAME = 'score-result-attachments-bucket';
    dynamoSend.mockResolvedValue({ Item: { id: { S: 'score-result-1' }, accountId: { S: 'account-1' } } });

    await expect(handler(event([{
      operation: 'READ', resourceType: 'SCORE_RESULT', resourceId: 'score-result-1', artifactType: 'SCORE_RESULT_ATTACHMENT', filename: 'evidence.json', contentType: 'application/json', sizeBytes: 42, sha256,
    }]) as any)).resolves.toEqual([expect.objectContaining({
      objectKey: 'scoreresults/score-result-1/evidence.json',
    })]);
  });

  it('rejects an API key identity without signing a URL', async () => {
    await expect(handler({
      arguments: { requests: [{
        operation: 'READ', resourceType: 'DATA_SET', resourceId: 'dataset-1', artifactType: 'DATASET_FILE', filename: 'training.csv', contentType: 'text/csv', sizeBytes: 42, sha256,
      }] },
      identity: { apiKey: 'not-an-identity' },
    } as any)).rejects.toThrow('Authenticated Cognito or IAM identity is required');

    expect(mockGetSignedUrl).not.toHaveBeenCalled();
  });

  it('rejects an empty Cognito claims object without signing a URL', async () => {
    await expect(handler({
      arguments: { requests: [{
        operation: 'READ', resourceType: 'DATA_SET', resourceId: 'dataset-1', artifactType: 'DATASET_FILE', filename: 'training.csv', contentType: 'text/csv', sizeBytes: 42, sha256,
      }] },
      identity: { claims: {} },
    } as any)).rejects.toThrow('Authenticated Cognito or IAM identity is required');

    expect(mockGetSignedUrl).not.toHaveBeenCalled();
  });

  it('rejects a batch larger than twenty without signing a URL', async () => {
    await expect(handler({
      arguments: { requests: Array.from({ length: 21 }, () => ({
      operation: 'READ', resourceType: 'DATA_SET', resourceId: 'dataset-1', artifactType: 'DATASET_FILE', filename: 'training.csv', contentType: 'text/csv', sizeBytes: 42, sha256,
      })) },
      identity: { claims: { sub: 'user-1' } },
    } as any)).rejects.toThrow();

    expect(mockGetSignedUrl).not.toHaveBeenCalled();
  });

  it.each([
    ['unsafe filename', { filename: '../escape.csv' }],
    ['invalid sha256', { sha256: `${sha256.slice(0, 63)}z` }],
    ['oversized write', { sizeBytes: 100 * 1024 * 1024 + 1 }],
    ['unsupported artifact type', { artifactType: 'UNSUPPORTED' }],
  ])('rejects %s before issuing a ticket', async (_reason, override) => {
    await expect(handler(event([{
      operation: 'WRITE',
      resourceType: 'DATA_SET',
      resourceId: 'dataset-1',
      artifactType: 'DATASET_FILE',
      filename: 'training.csv',
      contentType: 'text/csv',
      sizeBytes: 42,
      sha256,
      ...override,
    }]) as any)).rejects.toThrow();

    expect(mockGetSignedUrl).not.toHaveBeenCalled();
  });
});
