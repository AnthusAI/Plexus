import type { Logger } from '../types';
import type { Schema } from '../../data/resource';
import type { V6Client } from '@aws-amplify/api-graphql';

export async function fullCopy(
  tableName: string,
  productionClient: V6Client<Schema>,
  sandboxClient: V6Client<Schema>,
  accountId: string,
  logger: Logger
): Promise<number> {
  logger.table(tableName, 'Starting full copy');

  let copiedCount = 0;
  let nextToken: string | null | undefined = null;

  do {
    try {
      // Query production data (paginated)
      const result = await (productionClient.models as any)[tableName].list({
        filter: { accountId: { eq: accountId } },
        nextToken,
        limit: 100
      });

      const items = result.data || [];
      logger.progress(tableName, `Fetched ${items.length} items from production`);

      // Write to sandbox
      for (const item of items) {
        try {
          // Remove metadata fields that are auto-generated
          const { createdAt, updatedAt, owner, ...cleanItem } = item;

          await (sandboxClient.models as any)[tableName].create(cleanItem);
          copiedCount++;

          if (copiedCount % 10 === 0) {
            logger.progress(tableName, `Copied ${copiedCount} items`);
          }
        } catch (error: any) {
          // Skip items that already exist or fail validation
          if (!error.message?.includes('already exists')) {
            logger.warn(tableName, `Failed to copy item ${item.id}: ${error.message}`);
          }
        }
      }

      nextToken = result.nextToken;
    } catch (error: any) {
      logger.error(tableName, `Failed to fetch page: ${error.message}`);
      break;
    }
  } while (nextToken);

  logger.success(tableName, `Completed: ${copiedCount} items copied`);
  return copiedCount;
}
