import type { Logger } from '../types';
import type { Schema } from '../../data/resource';
import type { V6Client } from '@aws-amplify/api-graphql';
import { buildCreateInput, getPrimaryKeyInput, SkippedSeedItemError } from './create-input';

export { SkippedSeedItemError };

export async function createItem(
  client: V6Client<Schema>,
  tableName: string,
  item: Record<string, unknown>
): Promise<Record<string, unknown>> {
  const input = buildCreateInput(tableName, item);
  const result = await (client.models as any)[tableName].create(input);

  if (result.errors?.length) {
    const message = result.errors.map((error: any) => error.message).join('; ');

    if (message.includes('conditional request failed') && getPrimaryKeyInput(tableName, input)) {
      return input;
    }

    throw new Error(message);
  }

  if (!result.data) {
    throw new Error('Create returned no data');
  }

  return result.data;
}

export async function verifyCreatedSample(
  client: V6Client<Schema>,
  tableName: string,
  createdIds: string[],
  logger: Logger
): Promise<void> {
  const id = createdIds[0];

  if (!id) {
    return;
  }

  const result = await (client.models as any)[tableName].get({ id });

  if (result.errors?.length) {
    logger.warn(tableName, `Post-copy verification failed for ${id}: ${result.errors.map((error: any) => error.message).join('; ')}`);
    return;
  }

  if (!result.data) {
    logger.warn(tableName, `Post-copy verification could not read created item ${id}`);
    return;
  }

  logger.info(tableName, `Verified created item ${id}`);
}
