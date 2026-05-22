import type { Logger, TableConfig } from '../types';
import type { Schema } from '../../data/resource';
import type { V6Client } from '@aws-amplify/api-graphql';
import { getSeedItemLabel } from '../utils/create-input';
import { listAccountScopedPage } from '../utils/model-queries';
import { createItem, SkippedSeedItemError, verifyCreatedSample } from '../utils/write-result';

export type SampledRecords = {
  records: Record<string, unknown>[];
  recentCount: number;
};

export async function fetchSampledRecords(
  config: TableConfig,
  productionClient: V6Client<Schema>,
  accountId: string,
  daysRecent: number,
  logger: Logger
): Promise<SampledRecords> {
  const { name, recentCount = 1000, sampleCount = 1000, sortKey } = config;
  const maxItems = config.maxItems ?? recentCount + sampleCount;
  const cappedRecentCount = Math.min(recentCount, maxItems);
  const cappedSampleCount = Math.min(sampleCount, Math.max(0, maxItems - cappedRecentCount));

  logger.table(name, `Starting sampled copy (${cappedRecentCount} recent + ${cappedSampleCount} sampled, cap ${maxItems})`);

  if (config.enabled === false) {
    logger.info(name, 'Skipping because table is disabled in seed config');
    return { records: [], recentCount: 0 };
  }

  if (!sortKey) {
    logger.warn(name, 'No sortKey defined, cannot perform sampled copy');
    return { records: [], recentCount: 0 };
  }

  if (maxItems <= 0) {
    logger.info(name, 'Skipping because maxItems is 0');
    return { records: [], recentCount: 0 };
  }

  // Step 1: Copy recent items
  logger.progress(name, 'Fetching recent items...');
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - daysRecent);
  const cutoffISO = cutoffDate.toISOString();

  try {
    const records: Record<string, unknown>[] = [];
    const recentResult: any = await listAccountScopedPage(productionClient, name, accountId, {
      filter: { [sortKey]: { ge: cutoffISO } },
      limit: cappedRecentCount
    });

    const recentItems = recentResult.data || [];
    logger.progress(name, `Found ${recentItems.length} recent items`);
    records.push(...recentItems.slice(0, maxItems));

    // Step 2: Sample older items
    const remainingSampleCount = Math.min(cappedSampleCount, Math.max(0, maxItems - records.length));
    if (remainingSampleCount > 0) {
      logger.progress(name, 'Fetching older items for sampling...');

      const olderResult: any = await listAccountScopedPage(productionClient, name, accountId, {
        filter: { [sortKey]: { lt: cutoffISO } },
        limit: Math.min(5000, Math.max(remainingSampleCount * 3, remainingSampleCount))
      });

      const olderItems = olderResult.data || [];
      logger.progress(name, `Found ${olderItems.length} older items, sampling ${remainingSampleCount}...`);

      // Random sample
      const sampledIndices = new Set<number>();
      const targetSampleSize = Math.min(remainingSampleCount, olderItems.length);

      while (sampledIndices.size < targetSampleSize) {
        sampledIndices.add(Math.floor(Math.random() * olderItems.length));
      }

      for (const idx of sampledIndices) {
        if (records.length >= maxItems) {
          logger.info(name, `Stopped sampled fetch at configured cap of ${maxItems} items`);
          break;
        }

        records.push(olderItems[idx]);
      }
    }

    return {
      records,
      recentCount: recentItems.length
    };
  } catch (error: any) {
    logger.error(name, `Failed during sampled fetch: ${error.message}`);
  }

  return { records: [], recentCount: 0 };
}

export async function copySampledRecords(
  config: TableConfig,
  records: Record<string, unknown>[],
  sandboxClient: V6Client<Schema>,
  logger: Logger,
  recentCount = 0
): Promise<string[]> {
  const { name } = config;
  const createdIds: string[] = [];
  let copiedCount = 0;
  let recentCopiedCount = 0;

  for (let index = 0; index < records.length; index++) {
    const item = records[index];
    const itemLabel = getSeedItemLabel(name, item);
    const isRecent = index < recentCount;

    try {
      const created = await createItem(sandboxClient, name, item);
      if (typeof created.id === 'string') {
        createdIds.push(created.id);
      }
      copiedCount++;
      if (isRecent) {
        recentCopiedCount++;
      }
    } catch (error: any) {
      if (error instanceof SkippedSeedItemError) {
        logger.warn(name, `Skipped ${isRecent ? 'recent' : 'sampled'} item ${itemLabel}: ${error.message}`);
        continue;
      }

      if (!error.message?.includes('already exists')) {
        logger.warn(name, `Failed to copy ${isRecent ? 'recent' : 'sampled'} item ${itemLabel}: ${error.message}`);
      }
    }
  }

  logger.success(
    name,
    `Completed: ${copiedCount} items copied (${recentCopiedCount} recent + ${copiedCount - recentCopiedCount} sampled)`
  );
  await verifyCreatedSample(sandboxClient, name, createdIds, logger);

  return createdIds;
}

export async function sampledCopy(
  config: TableConfig,
  productionClient: V6Client<Schema>,
  sandboxClient: V6Client<Schema>,
  accountId: string,
  daysRecent: number,
  logger: Logger
): Promise<string[]> {
  const { records, recentCount } = await fetchSampledRecords(config, productionClient, accountId, daysRecent, logger);
  return copySampledRecords(config, records, sandboxClient, logger, recentCount);
}
