import type { Logger, TableConfig } from '../types';
import type { Schema } from '../../data/resource';
import type { V6Client } from '@aws-amplify/api-graphql';

export async function recentCopy(
  config: TableConfig,
  productionClient: V6Client<Schema>,
  sandboxClient: V6Client<Schema>,
  accountId: string,
  daysRecent: number,
  logger: Logger
): Promise<number> {
  const { name, sortKey } = config;
  logger.table(name, `Starting recent copy (last ${daysRecent} days)`);

  if (!sortKey) {
    logger.warn(name, 'No sortKey defined, falling back to full copy');
    return 0;
  }

  // Calculate cutoff date
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - daysRecent);
  const cutoffISO = cutoffDate.toISOString();

  let copiedCount = 0;
  let nextToken: string | null | undefined = null;

  do {
    try {
      // Query using filter with time constraint
      const result = await (productionClient.models as any)[name].list({
        filter: {
          accountId: { eq: accountId },
          [sortKey]: { ge: cutoffISO }
        },
        nextToken,
        limit: 100
      });

      const items = result.data || [];
      logger.progress(name, `Fetched ${items.length} recent items`);

      for (const item of items) {
        try {
          const { createdAt, updatedAt, owner, ...cleanItem } = item;
          await (sandboxClient.models as any)[name].create(cleanItem);
          copiedCount++;

          if (copiedCount % 10 === 0) {
            logger.progress(name, `Copied ${copiedCount} items`);
          }
        } catch (error: any) {
          if (!error.message?.includes('already exists')) {
            logger.warn(name, `Failed to copy item ${item.id}: ${error.message}`);
          }
        }
      }

      nextToken = result.nextToken;
    } catch (error: any) {
      logger.error(name, `Failed to fetch page: ${error.message}`);
      break;
    }
  } while (nextToken);

  logger.success(name, `Completed: ${copiedCount} recent items copied`);
  return copiedCount;
}
