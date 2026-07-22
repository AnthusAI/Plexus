import type { Logger, TableConfig } from '../types';
import type { Schema } from '../../data/resource';
import type { V6Client } from '@aws-amplify/api-graphql';
import { getSeedItemLabel } from '../utils/create-input';
import { listAccountScopedPage } from '../utils/model-queries';
import { createItem, SkippedSeedItemError, verifyCreatedSample } from '../utils/write-result';

export async function recentCopy(
  config: TableConfig,
  productionClient: V6Client<Schema>,
  sandboxClient: V6Client<Schema>,
  accountId: string,
  daysRecent: number,
  logger: Logger
): Promise<string[]> {
  const { name, sortKey } = config;
  logger.table(name, `Starting recent copy (last ${daysRecent} days)`);

  if (config.enabled === false) {
    logger.info(name, 'Skipping because table is disabled in seed config');
    return [];
  }

  if (!sortKey) {
    logger.warn(name, 'No sortKey defined, falling back to full copy');
    return [];
  }

  const maxItems = config.maxItems ?? 500;
  const pageSize = config.pageSize ?? 100;

  if (maxItems <= 0) {
    logger.info(name, 'Skipping because maxItems is 0');
    return [];
  }

  // Calculate cutoff date
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - daysRecent);
  const cutoffISO = cutoffDate.toISOString();

  let copiedCount = 0;
  let attemptedCount = 0;
  const createdIds: string[] = [];
  let nextToken: string | null | undefined = null;
  const seenNextTokens = new Set<string>();

  do {
    try {
      const remaining = maxItems - attemptedCount;
      if (remaining <= 0) {
        logger.info(name, `Reached configured cap of ${maxItems} items`);
        break;
      }

      // Query production data using an account index when the model exposes one.
      const result: any = await listAccountScopedPage(productionClient, name, accountId, {
        filter: { [sortKey]: { ge: cutoffISO } },
        nextToken,
        limit: Math.min(pageSize, remaining)
      });

      const items = result.data || [];
      logger.progress(name, `Fetched ${items.length} recent items`);

      for (const item of items) {
        attemptedCount++;
        const itemLabel = getSeedItemLabel(name, item);

        try {
          const created = await createItem(sandboxClient, name, item);
          if (typeof created.id === 'string') {
            createdIds.push(created.id);
          }
          copiedCount++;

          if (copiedCount % 10 === 0) {
            logger.progress(name, `Copied ${copiedCount} items`);
          }
        } catch (error: any) {
          if (error instanceof SkippedSeedItemError) {
            logger.warn(name, `Skipped item ${itemLabel}: ${error.message}`);
            continue;
          }

          if (!error.message?.includes('already exists')) {
            logger.warn(name, `Failed to copy item ${itemLabel}: ${error.message}`);
          }
        }
      }

      nextToken = result.nextToken;
      // Protect long-running seeds from an API that returns a stale cursor.
      // This can otherwise spin forever when a filtered query yields no rows.
      if (nextToken && seenNextTokens.has(nextToken)) {
        logger.warn(name, 'Stopping because pagination returned a repeated continuation token');
        break;
      }
      if (nextToken) {
        seenNextTokens.add(nextToken);
      }
      if (nextToken && attemptedCount >= maxItems) {
        logger.info(name, `Stopped at configured cap of ${maxItems} items`);
        break;
      }
    } catch (error: any) {
      logger.error(name, `Failed to fetch page: ${error.message}`);
      break;
    }
  } while (nextToken);

  logger.success(name, `Completed: ${copiedCount} recent items copied`);
  await verifyCreatedSample(sandboxClient, name, createdIds, logger);
  return createdIds;
}
