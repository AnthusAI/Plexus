import type { Logger, TableConfig } from '../types';
import type { Schema } from '../../data/resource';
import type { V6Client } from '@aws-amplify/api-graphql';
import { getSeedItemLabel } from '../utils/create-input';
import { listAccountScopedPage } from '../utils/model-queries';
import { createItem, SkippedSeedItemError, verifyCreatedSample } from '../utils/write-result';

type PageFetcher = (options: { nextToken?: string | null; limit: number }) => Promise<any>;
type CopyLimitOptions = {
  enabled?: boolean;
  maxItems?: number;
  maxPerParent?: number;
  pageSize?: number;
  preferFeatured?: boolean;
  queryArgs?: Record<string, unknown>;
};
type CopyPagesResult = {
  createdIds: string[];
  attemptedCount: number;
};

function selectItemsForCopy(items: any[], options: CopyLimitOptions, limit: number): any[] {
  if (!options.preferFeatured) {
    return items.slice(0, limit);
  }

  const selected: any[] = [];
  const selectedIds = new Set<string>();
  const featured = items.find((item) => item?.isFeatured === true || item?.isFeatured === 'true');

  if (featured) {
    selected.push(featured);
    if (typeof featured.id === 'string') {
      selectedIds.add(featured.id);
    }
  }

  for (const item of items) {
    if (selected.length >= limit) {
      break;
    }

    if (typeof item?.id === 'string' && selectedIds.has(item.id)) {
      continue;
    }

    selected.push(item);
  }

  return selected;
}

async function copyPages(
  tableName: string,
  sandboxClient: V6Client<Schema>,
  logger: Logger,
  fetchPage: PageFetcher,
  options: { rethrowFetchError?: boolean } & CopyLimitOptions = {}
): Promise<CopyPagesResult> {
  logger.table(tableName, 'Starting full copy');

  if (options.enabled === false) {
    logger.info(tableName, 'Skipping because table is disabled in seed config');
    return { createdIds: [], attemptedCount: 0 };
  }

  const maxItems = options.maxItems ?? 500;
  const pageSize = options.pageSize ?? 100;

  if (maxItems <= 0) {
    logger.info(tableName, 'Skipping because maxItems is 0');
    return { createdIds: [], attemptedCount: 0 };
  }

  let copiedCount = 0;
  let attemptedCount = 0;
  const createdIds: string[] = [];
  let nextToken: string | null | undefined = null;

  do {
    try {
      const remaining = maxItems - attemptedCount;
      if (remaining <= 0) {
        logger.info(tableName, `Reached configured cap of ${maxItems} items`);
        break;
      }

      const result: any = await fetchPage({
        nextToken,
        limit: Math.min(pageSize, remaining)
      });

      const items = result.data || [];
      logger.progress(tableName, `Fetched ${items.length} items from production`);
      const selectedItems = selectItemsForCopy(items, options, remaining);

      // Write to sandbox
      for (const item of selectedItems) {
        attemptedCount++;
        const itemLabel = getSeedItemLabel(tableName, item);

        try {
          const created = await createItem(sandboxClient, tableName, item);
          if (typeof created.id === 'string') {
            createdIds.push(created.id);
          }
          copiedCount++;

          if (copiedCount % 10 === 0) {
            logger.progress(tableName, `Copied ${copiedCount} items`);
          }
        } catch (error: any) {
          if (error instanceof SkippedSeedItemError) {
            logger.warn(tableName, `Skipped item ${itemLabel}: ${error.message}`);
            continue;
          }

          // Skip items that already exist or fail validation
          if (!error.message?.includes('already exists')) {
            logger.warn(tableName, `Failed to copy item ${itemLabel}: ${error.message}`);
          }
        }
      }

      nextToken = result.nextToken;
      if (nextToken && attemptedCount >= maxItems) {
        logger.info(tableName, `Stopped at configured cap of ${maxItems} items`);
        break;
      }
    } catch (error: any) {
      logger.error(tableName, `Failed to fetch page: ${error.message}`);
      if (options.rethrowFetchError) {
        throw error;
      }
      break;
    }
  } while (nextToken);

  logger.success(tableName, `Completed: ${copiedCount} items copied`);
  await verifyCreatedSample(sandboxClient, tableName, createdIds, logger);
  return { createdIds, attemptedCount };
}

export async function fullCopy(
  tableName: string,
  productionClient: V6Client<Schema>,
  sandboxClient: V6Client<Schema>,
  accountId: string,
  logger: Logger,
  options: TableConfig | CopyLimitOptions = {}
): Promise<string[]> {
  const result = await copyPages(
    tableName,
    sandboxClient,
    logger,
    async ({ nextToken, limit }) => {
      const result = await listAccountScopedPage(productionClient, tableName, accountId, {
        nextToken,
        limit
      });

      if (tableName === 'Account' && (result.data || []).length === 0) {
        throw new Error(`Production account ${accountId} was not found`);
      }

      return result;
    },
    { ...options, rethrowFetchError: tableName === 'Account' }
  );

  return result.createdIds;
}

export async function fullCopyByParent(
  tableName: string,
  parentIds: string[],
  queryName: string,
  queryKey: string,
  productionClient: V6Client<Schema>,
  sandboxClient: V6Client<Schema>,
  logger: Logger,
  options: TableConfig | CopyLimitOptions = {}
): Promise<string[]> {
  const allCreatedIds: string[] = [];
  let attemptedCount = 0;

  if (options.enabled === false) {
    logger.info(tableName, 'Skipping because table is disabled in seed config');
    return [];
  }

  const maxItems = options.maxItems ?? 500;
  const maxPerParent = options.maxPerParent ?? 25;

  for (const parentId of parentIds) {
    const remaining = maxItems - attemptedCount;
    if (remaining <= 0) {
      logger.info(tableName, `Stopped parent traversal at configured cap of ${maxItems} items`);
      break;
    }

    const result = await copyPages(
      tableName,
      sandboxClient,
      logger,
      ({ nextToken, limit }) => {
        const query = (productionClient.models as any)[tableName][queryName];

        if (typeof query !== 'function') {
          throw new Error(`No query ${queryName} is configured for ${tableName}`);
        }

        return query({
          [queryKey]: parentId,
          nextToken,
          limit,
          ...options.queryArgs
        });
      },
      {
        maxItems: Math.min(maxPerParent, remaining),
        pageSize: options.pageSize,
        preferFeatured: options.preferFeatured
      }
    );

    allCreatedIds.push(...result.createdIds);
    attemptedCount += result.attemptedCount;
  }

  return allCreatedIds;
}

export async function fullCopyByIds(
  tableName: string,
  ids: string[],
  productionClient: V6Client<Schema>,
  sandboxClient: V6Client<Schema>,
  logger: Logger,
  options: TableConfig | CopyLimitOptions = {}
): Promise<string[]> {
  logger.table(tableName, `Starting id-based copy (${ids.length} candidate ids)`);

  if (options.enabled === false) {
    logger.info(tableName, 'Skipping because table is disabled in seed config');
    return [];
  }

  const maxItems = options.maxItems ?? 500;
  const createdIds: string[] = [];
  let attemptedCount = 0;

  for (const id of [...new Set(ids)]) {
    if (attemptedCount >= maxItems) {
      logger.info(tableName, `Stopped id-based copy at configured cap of ${maxItems} items`);
      break;
    }

    attemptedCount++;

    try {
      const result = await (productionClient.models as any)[tableName].get({ id });
      const item = result.data;

      if (!item) {
        logger.warn(tableName, `Source item ${id} was not found`);
        continue;
      }

      const created = await createItem(sandboxClient, tableName, item);
      if (typeof created.id === 'string') {
        createdIds.push(created.id);
      }

      if (createdIds.length % 10 === 0) {
        logger.progress(tableName, `Copied ${createdIds.length} items`);
      }
    } catch (error: any) {
      if (error instanceof SkippedSeedItemError) {
        logger.warn(tableName, `Skipped item ${id}: ${error.message}`);
        continue;
      }

      if (!error.message?.includes('already exists')) {
        logger.warn(tableName, `Failed to copy item ${id}: ${error.message}`);
      }
    }
  }

  logger.success(tableName, `Completed: ${createdIds.length} items copied`);
  await verifyCreatedSample(sandboxClient, tableName, createdIds, logger);
  return createdIds;
}
