import { readFileSync } from 'node:fs';

type ModelField = {
  association?: unknown;
  isRequired?: boolean;
};

type ModelIntrospection = {
  models: Record<string, {
    fields: Record<string, ModelField>;
    attributes?: Array<{
      type?: string;
      properties?: {
        name?: string;
        fields?: string[];
      };
    }>;
    primaryKeyInfo?: {
      primaryKeyFieldName?: string;
      sortKeyFieldNames?: string[];
    };
  }>;
};

const outputs = JSON.parse(
  readFileSync(new URL('../../../amplify_outputs.json', import.meta.url), { encoding: 'utf8' })
) as {
  data?: {
    model_introspection?: ModelIntrospection;
  };
};

const metadataFields = new Set(['createdAt', 'updatedAt', 'owner']);
const autoTimestampFields = new Set(['createdAt', 'updatedAt']);

export class SkippedSeedItemError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'SkippedSeedItemError';
  }
}

function normalizeValue(tableName: string, fieldName: string, value: unknown): unknown {
  if (tableName === 'ScoreVersion' && fieldName === 'isFeatured' && (value === undefined || value === null)) {
    return 'false';
  }

  if (tableName === 'ScoreResult' && fieldName === 'status' && (value === undefined || value === null)) {
    return 'UNKNOWN';
  }

  return value;
}

export function buildCreateInput(tableName: string, item: Record<string, unknown>): Record<string, unknown> {
  const model = outputs.data?.model_introspection?.models[tableName];
  const fields = model?.fields;

  if (!fields) {
    throw new Error(`No model introspection found for ${tableName}`);
  }

  const input: Record<string, unknown> = {};
  const missingRequiredFields: string[] = [];

  for (const [fieldName, field] of Object.entries(fields)) {
    if (metadataFields.has(fieldName) || field.association) {
      continue;
    }

    const value = normalizeValue(tableName, fieldName, item[fieldName]);

    if (value === undefined || value === null) {
      if (field.isRequired) {
        missingRequiredFields.push(fieldName);
      }
      continue;
    }

    input[fieldName] = value;
  }

  if (missingRequiredFields.length > 0) {
    throw new Error(`Required fields are null or missing: ${missingRequiredFields.join(', ')}`);
  }

  const missingCompositeKeyFields = findMissingCompositeKeyFields(model?.attributes || [], input);
  if (missingCompositeKeyFields.length > 0) {
    throw new SkippedSeedItemError(`Skipping item with incomplete composite index fields: ${missingCompositeKeyFields.join(', ')}`);
  }

  return input;
}

export function getPrimaryKeyInput(tableName: string, input: Record<string, unknown>): Record<string, unknown> | null {
  const primaryKeyInfo = outputs.data?.model_introspection?.models[tableName]?.primaryKeyInfo;
  const primaryKeyFieldName = primaryKeyInfo?.primaryKeyFieldName || 'id';
  const keyFieldNames = [primaryKeyFieldName, ...(primaryKeyInfo?.sortKeyFieldNames || [])];
  const keyInput: Record<string, unknown> = {};

  for (const fieldName of keyFieldNames) {
    const value = input[fieldName];

    if (value === undefined || value === null) {
      return null;
    }

    keyInput[fieldName] = value;
  }

  return keyInput;
}

export function getSeedItemLabel(tableName: string, item: Record<string, unknown>): string {
  const keyInput = getPrimaryKeyInput(tableName, item);

  if (keyInput) {
    return Object.values(keyInput).join('/');
  }

  if (typeof item.id === 'string') {
    return item.id;
  }

  return 'unknown';
}

function findMissingCompositeKeyFields(
  attributes: Array<{ type?: string; properties?: { name?: string; fields?: string[] } }>,
  input: Record<string, unknown>
): string[] {
  const missingFields = new Set<string>();

  for (const attribute of attributes) {
    if (attribute.type !== 'key') {
      continue;
    }

    const keyFields = attribute.properties?.fields || [];
    if (keyFields.length <= 1) {
      continue;
    }

    const partitionKey = keyFields[0];
    if (input[partitionKey] === undefined || input[partitionKey] === null) {
      continue;
    }

    const nonTimestampFields = keyFields.filter((fieldName) => !autoTimestampFields.has(fieldName));
    const providedFields = nonTimestampFields.filter((fieldName) => input[fieldName] !== undefined && input[fieldName] !== null);

    if (providedFields.length === 0 || providedFields.length === nonTimestampFields.length) {
      continue;
    }

    for (const fieldName of nonTimestampFields) {
      if (input[fieldName] === undefined || input[fieldName] === null) {
        missingFields.add(`${attribute.properties?.name || keyFields.join('+')}.${fieldName}`);
      }
    }
  }

  return [...missingFields];
}
