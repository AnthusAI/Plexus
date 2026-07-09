import type { Schema } from '../resource';
import { PutObjectCommand, S3Client } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

const DEFAULT_TTL_SECONDS = 900;
const MAX_TTL_SECONDS = 3600;

type ScopeConfig = {
  bucketEnv: string;
  keyPrefix: string;
};

const SCOPE_CONFIG: Record<string, ScopeConfig> = {
  SCORE_RESULT: {
    bucketEnv: 'SCORE_RESULT_ATTACHMENTS_BUCKET_NAME',
    keyPrefix: 'scoreresults',
  },
  EVALUATION: {
    bucketEnv: 'SCORE_RESULT_ATTACHMENTS_BUCKET_NAME',
    keyPrefix: 'evaluations',
  },
  REPORT_BLOCK: {
    bucketEnv: 'REPORT_BLOCK_DETAILS_BUCKET_NAME',
    keyPrefix: 'reportblocks',
  },
};

const FALLBACK_BUCKETS: Record<string, string> = {
  SCORE_RESULT_ATTACHMENTS_BUCKET_NAME: 'scoreresultattachments-production',
  REPORT_BLOCK_DETAILS_BUCKET_NAME: 'reportblockdetails-production',
};

function sanitizePathSegment(input: string, fieldName: string): string {
  const trimmed = (input || '').trim();
  if (!trimmed) {
    throw new Error(`${fieldName} is required`);
  }
  if (trimmed.includes('..') || trimmed.includes('/') || trimmed.includes('\\')) {
    throw new Error(`${fieldName} contains invalid path characters`);
  }
  if (!/^[A-Za-z0-9._:-]+$/.test(trimmed)) {
    throw new Error(`${fieldName} contains unsupported characters`);
  }
  return trimmed;
}

function resolveTtlSeconds(): number {
  const raw = Number.parseInt((process.env.UPLOAD_URL_TTL_SECONDS || '').trim(), 10);
  if (Number.isNaN(raw) || raw <= 0) {
    return DEFAULT_TTL_SECONDS;
  }
  return Math.min(raw, MAX_TTL_SECONDS);
}

export const handler: Schema['requestAttachmentUpload']['functionHandler'] = async (event) => {
  const scope = (event.arguments.scope || '').trim().toUpperCase();
  const ownerId = sanitizePathSegment(event.arguments.ownerId, 'ownerId');
  const fileName = sanitizePathSegment(event.arguments.fileName, 'fileName');
  const contentType = (event.arguments.contentType || 'application/octet-stream').trim();

  const scopeConfig = SCOPE_CONFIG[scope];
  if (!scopeConfig) {
    throw new Error(`Unsupported attachment scope: ${event.arguments.scope}`);
  }

  const bucketName = (process.env[scopeConfig.bucketEnv] || FALLBACK_BUCKETS[scopeConfig.bucketEnv] || '').trim();
  if (!bucketName) {
    throw new Error(`Missing bucket configuration for scope: ${scope}`);
  }

  const key = `${scopeConfig.keyPrefix}/${ownerId}/${fileName}`;
  const region = (process.env.AWS_REGION || 'us-east-1').trim();
  const ttlSeconds = resolveTtlSeconds();
  const expiresAt = new Date(Date.now() + ttlSeconds * 1000).toISOString();

  const s3Client = new S3Client({ region });
  const putObjectCommand = new PutObjectCommand({
    Bucket: bucketName,
    Key: key,
    ContentType: contentType,
  });

  const uploadUrl = await getSignedUrl(s3Client as any, putObjectCommand, {
    expiresIn: ttlSeconds,
  });

  return {
    key,
    uploadUrl,
    method: 'PUT',
    headers: {
      'Content-Type': contentType,
    },
    contentType,
    expiresAt,
  };
};
