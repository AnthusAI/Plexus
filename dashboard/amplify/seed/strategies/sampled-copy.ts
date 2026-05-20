import type { Logger, TableConfig } from '../types';
import type { Schema } from '../../data/resource';
import type { V6Client } from '@aws-amplify/api-graphql';

export async function sampledCopy(
  config: TableConfig,
  productionClient: V6Client<Schema>,
  sandboxClient: V6Client<Schema>,
  accountId: string,
  daysRecent: number,
  logger: Logger
): Promise<number> {
  const { name, recentCount = 1000, sampleCount = 1000, sortKey } = config;
  logger.table(name, `Starting sampled copy (${recentCount} recent + ${sampleCount} sampled)`);

  if (!sortKey) {
    logger.warn(name, 'No sortKey defined, cannot perform sampled copy');
    return 0;
  }

  let copiedCount = 0;

  // Step 1: Copy recent items
  logger.progress(name, 'Fetching recent items...');
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - daysRecent);
  const cutoffISO = cutoffDate.toISOString();

  try {
    const recentResult = await (productionClient.models as any)[name].list({
      filter: {
        accountId: { eq: accountId },
        [sortKey]: { ge: cutoffISO }
      },
      limit: recentCount
    });

    const recentItems = recentResult.data || [];
    logger.progress(name, `Found ${recentItems.length} recent items`);

    for (const item of recentItems) {
      try {
        const { createdAt, updatedAt, owner, ...cleanItem } = item;
        await (sandboxClient.models as any)[name].create(cleanItem);
        copiedCount++;
      } catch (error: any) {
        if (!error.message?.includes('already exists')) {
          logger.warn(name, `Failed to copy recent item ${item.id}: ${error.message}`);
        }
      }
    }

    // Step 2: Sample older items
    if (sampleCount > 0) {
      logger.progress(name, 'Fetching older items for sampling...');

      const olderResult = await (productionClient.models as any)[name].list({
        filter: {
          accountId: { eq: accountId },
          [sortKey]: { lt: cutoffISO }
        },
        limit: 5000 // Fetch pool for sampling
      });

      const olderItems = olderResult.data || [];
      logger.progress(name, `Found ${olderItems.length} older items, sampling ${sampleCount}...`);

      // Random sample
      const sampledIndices = new Set<number>();
      const targetSampleSize = Math.min(sampleCount, olderItems.length);

      while (sampledIndices.size < targetSampleSize) {
        sampledIndices.add(Math.floor(Math.random() * olderItems.length));
      }

      for (const idx of sampledIndices) {
        try {
          const item = olderItems[idx];
          const { createdAt, updatedAt, owner, ...cleanItem } = item;
          await (sandboxClient.models as any)[name].create(cleanItem);
          copiedCount++;
        } catch (error: any) {
          if (!error.message?.includes('already exists')) {
            logger.warn(name, `Failed to copy sampled item: ${error.message}`);
          }
        }
      }
    }

    logger.success(
      name,
      `Completed: ${copiedCount} items copied (${recentItems.length} recent + ${copiedCount - recentItems.length} sampled)`
    );
  } catch (error: any) {
    logger.error(name, `Failed during sampled copy: ${error.message}`);
  }

  return copiedCount;
}
