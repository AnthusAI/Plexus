import { GetItemCommand, DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { GetObjectCommand, PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

const MAX_BATCH_SIZE = 20;
const MAX_WRITE_BYTES = 100 * 1024 * 1024;
const URL_TTL_SECONDS = 5 * 60;

type Operation = 'READ' | 'WRITE';
type ResourceType = 'DATA_SET' | 'PROCEDURE' | 'SCORE_RESULT' | 'EVALUATION' | 'TASK';
type ArtifactType =
  | 'DATASET_FILE'
  | 'PROCEDURE_ATTACHMENT'
  | 'PROCEDURE_DASHBOARD_STATE'
  | 'SCORE_RESULT_ATTACHMENT'
  | 'EVALUATION_RCA'
  | 'TASK_ATTACHMENT';

type TransferRequest = {
  operation: Operation;
  resourceType: ResourceType;
  resourceId: string;
  artifactType: ArtifactType;
  filename: string;
  contentType: string;
  sizeBytes: number;
  sha256: string;
};

type ArtifactRoute = {
  resourceType: ResourceType;
  artifactType: ArtifactType;
  bucketEnv: string;
  keyPrefix: string;
  tableEnv: string;
  accountScoped?: boolean;
};

const ROUTES: Record<ArtifactType, ArtifactRoute> = {
  DATASET_FILE: {
    resourceType: 'DATA_SET',
    artifactType: 'DATASET_FILE',
    bucketEnv: 'DATA_SOURCES_BUCKET_NAME',
    keyPrefix: 'datasets',
    tableEnv: 'DATA_SET_TABLE_NAME',
    accountScoped: true,
  },
  PROCEDURE_ATTACHMENT: {
    resourceType: 'PROCEDURE',
    artifactType: 'PROCEDURE_ATTACHMENT',
    bucketEnv: 'REPORT_BLOCK_DETAILS_BUCKET_NAME',
    keyPrefix: 'procedures',
    tableEnv: 'PROCEDURE_TABLE_NAME',
  },
  PROCEDURE_DASHBOARD_STATE: {
    resourceType: 'PROCEDURE',
    artifactType: 'PROCEDURE_DASHBOARD_STATE',
    bucketEnv: 'REPORT_BLOCK_DETAILS_BUCKET_NAME',
    keyPrefix: 'reportblocks/procedures',
    tableEnv: 'PROCEDURE_TABLE_NAME',
  },
  SCORE_RESULT_ATTACHMENT: {
    resourceType: 'SCORE_RESULT',
    artifactType: 'SCORE_RESULT_ATTACHMENT',
    bucketEnv: 'SCORE_RESULT_ATTACHMENTS_BUCKET_NAME',
    keyPrefix: 'scoreresults',
    tableEnv: 'SCORE_RESULT_TABLE_NAME',
  },
  EVALUATION_RCA: {
    resourceType: 'EVALUATION',
    artifactType: 'EVALUATION_RCA',
    bucketEnv: 'SCORE_RESULT_ATTACHMENTS_BUCKET_NAME',
    keyPrefix: 'evaluations',
    tableEnv: 'EVALUATION_TABLE_NAME',
  },
  TASK_ATTACHMENT: {
    resourceType: 'TASK',
    artifactType: 'TASK_ATTACHMENT',
    bucketEnv: 'TASK_ATTACHMENTS_BUCKET_NAME',
    keyPrefix: 'tasks',
    tableEnv: 'TASK_TABLE_NAME',
  },
};

const dynamo = new DynamoDBClient({});
const s3 = new S3Client({});

const record = (value: unknown): Record<string, unknown> | undefined => (
  typeof value === 'object' && value !== null ? value as Record<string, unknown> : undefined
);

function requiredString(value: unknown, field: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`${field} is required`);
  }
  return value.trim();
}

function validateRequest(value: unknown): TransferRequest {
  const request = record(value);
  if (!request) throw new Error('Each transfer request must be an object');

  const operation = requiredString(request.operation, 'operation') as Operation;
  const resourceType = requiredString(request.resourceType, 'resourceType') as ResourceType;
  const resourceId = requiredString(request.resourceId, 'resourceId');
  const artifactType = requiredString(request.artifactType, 'artifactType') as ArtifactType;
  const filename = requiredString(request.filename, 'filename');
  const contentType = requiredString(request.contentType, 'contentType').toLowerCase();
  const sizeBytes = request.sizeBytes;
  const sha256 = requiredString(request.sha256, 'sha256').toLowerCase();

  if (operation !== 'READ' && operation !== 'WRITE') {
    throw new Error('operation must be READ or WRITE');
  }
  const route = ROUTES[artifactType];
  if (!route) throw new Error(`Unsupported artifactType: ${artifactType}`);
  if (route.resourceType !== resourceType) {
    throw new Error(`artifactType ${artifactType} is not allowed for ${resourceType}`);
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$/.test(resourceId)) {
    throw new Error('resourceId contains unsupported characters');
  }
  const filenameSegments = filename.split('/');
  if (filename.startsWith('/') || filename.endsWith('/') || filenameSegments.some((segment) => (
    !/^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$/.test(segment) || segment === '.' || segment === '..'
  ))) {
    throw new Error('filename contains unsupported characters');
  }
  if (artifactType === 'PROCEDURE_DASHBOARD_STATE' && filename !== 'dashboard_state.json') {
    throw new Error('PROCEDURE_DASHBOARD_STATE must use dashboard_state.json');
  }
  if (artifactType === 'EVALUATION_RCA' && filename !== 'root_cause.full.json') {
    throw new Error('EVALUATION_RCA must use root_cause.full.json');
  }
  if (!/^[a-z0-9][a-z0-9!#$&^_.+-]*\/[a-z0-9][a-z0-9!#$&^_.+-]*$/.test(contentType)) {
    throw new Error('contentType must be a valid media type');
  }
  if (typeof sizeBytes !== 'number' || !Number.isSafeInteger(sizeBytes) || sizeBytes < 0) {
    throw new Error('sizeBytes must be a nonnegative integer');
  }
  if (operation === 'WRITE' && sizeBytes > MAX_WRITE_BYTES) {
    throw new Error('WRITE sizeBytes cannot exceed 100 MiB');
  }
  if (!/^[a-f0-9]{64}$/.test(sha256)) {
    throw new Error('sha256 must be a hexadecimal SHA-256 digest');
  }

  return { operation, resourceType, resourceId, artifactType, filename, contentType, sizeBytes, sha256 };
}

function trustedAccountId(identity: unknown): string | undefined {
  const identityRecord = record(identity);
  const claims = record(identityRecord?.claims);
  const resolverContext = record(identityRecord?.resolverContext);
  const claim = claims?.['custom:account_id'] ?? claims?.['custom:accountId'] ?? resolverContext?.accountId;
  return typeof claim === 'string' && claim.trim() ? claim.trim() : undefined;
}

function assertAuthenticatedIdentity(identity: unknown): void {
  const identityRecord = record(identity);
  const claims = record(identityRecord?.claims);
  const hasUserPoolIdentity = typeof claims?.sub === 'string' || typeof claims?.username === 'string';
  const hasIamIdentity = typeof identityRecord?.userArn === 'string' && typeof identityRecord?.accountId === 'string';
  if (!hasUserPoolIdentity && !hasIamIdentity) {
    throw new Error('Authenticated Cognito or IAM identity is required');
  }
}

async function assertResourceAccess(request: TransferRequest, identity: unknown): Promise<{ bucket: string; objectKey: string }> {
  const route = ROUTES[request.artifactType];
  const tableName = requiredString(process.env[route.tableEnv], route.tableEnv);
  const result = await dynamo.send(new GetItemCommand({
    TableName: tableName,
    Key: { id: { S: request.resourceId } },
    ConsistentRead: true,
  }));
  const item = result.Item;
  const accountId = item?.accountId?.S;
  if (!item || !accountId) {
    throw new Error('Requested resource was not found or is not transfer-authorized');
  }
  const callerAccountId = trustedAccountId(identity);
  if (callerAccountId && callerAccountId !== accountId) {
    throw new Error('Requested resource belongs to a different account');
  }

  const bucket = requiredString(process.env[route.bucketEnv], route.bucketEnv);
  const objectKey = route.accountScoped
    ? `${route.keyPrefix}/${accountId}/${request.resourceId}/${request.filename}`
    : `${route.keyPrefix}/${request.resourceId}/${request.filename}`;
  return { bucket, objectKey };
}

function writeHeaders(contentType: string, sizeBytes: number, sha256: string): Record<string, string> {
  return {
    'content-type': contentType,
    'content-length': String(sizeBytes),
    'x-amz-checksum-sha256': Buffer.from(sha256, 'hex').toString('base64'),
  };
}

type ArtifactTransferTicketEvent = {
  arguments: { requests: unknown[] };
  identity?: unknown;
};

export const handler = async (event: ArtifactTransferTicketEvent) => {
  assertAuthenticatedIdentity(event.identity);
  const requests = event.arguments.requests;
  if (!Array.isArray(requests) || requests.length === 0 || requests.length > MAX_BATCH_SIZE) {
    throw new Error('requests must contain between 1 and 20 transfer requests');
  }

  return Promise.all(requests.map(async (rawRequest) => {
    const request = validateRequest(rawRequest);
    const { bucket, objectKey } = await assertResourceAccess(request, event.identity);
    const expiresAt = new Date(Date.now() + URL_TTL_SECONDS * 1000).toISOString();

    if (request.operation === 'READ') {
      const url = await getSignedUrl(s3, new GetObjectCommand({ Bucket: bucket, Key: objectKey }), {
        expiresIn: URL_TTL_SECONDS,
      });
      return { objectKey, method: 'GET', url, requiredHeaders: {}, expiresAt };
    }

    const requiredHeaders = writeHeaders(request.contentType, request.sizeBytes, request.sha256);
    const url = await getSignedUrl(s3, new PutObjectCommand({
      Bucket: bucket,
      Key: objectKey,
      ContentType: request.contentType,
      ContentLength: request.sizeBytes,
      ChecksumSHA256: requiredHeaders['x-amz-checksum-sha256'],
    }), { expiresIn: URL_TTL_SECONDS });
    return { objectKey, method: 'PUT', url, requiredHeaders, expiresAt };
  }));
};
