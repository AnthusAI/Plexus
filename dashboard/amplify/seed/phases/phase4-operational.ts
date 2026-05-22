import type { SeedContext } from '../types';
import { fullCopyByIds, fullCopyByParent } from '../strategies/full-copy';
import { recentCopy } from '../strategies/recent-copy';
import { fetchSampledRecords } from '../strategies/sampled-copy';

export async function seedPhase4(context: SeedContext): Promise<void> {
  const { sandboxClient, productionClient, accountId, daysRecent, config, logger } = context;

  logger.phase('Phase 4: Operational & Large-Scale Data');

  // Operational tables (recent data only)
  context.copiedIds['Task'] = await recentCopy(
    config.tables['Task'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  context.copiedIds['Evaluation'] = await recentCopy(
    config.tables['Evaluation'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  // Use ScoringJob as the anchor for Item sampling. Some production Item rows
  // are not discoverable through the generic account/time Item indexes, but
  // ScoringJob carries the Item relationship needed for a useful sandbox slice.
  const scoringJobSample = await fetchSampledRecords(
    config.tables['ScoringJob'],
    productionClient,
    accountId,
    daysRecent,
    logger
  );
  const scoringJobItemIds = scoringJobSample.records
    .map((record) => record.itemId)
    .filter((itemId): itemId is string => typeof itemId === 'string');

  context.copiedIds['Item'] = await fullCopyByIds(
    'Item',
    scoringJobItemIds,
    productionClient,
    sandboxClient,
    logger,
    config.tables['Item']
  );

  if ((context.copiedIds['Item'] || []).length === 0) {
    logger.warn('ScoringJob', 'Skipping because no Item records were copied');
    context.copiedIds['ScoringJob'] = [];
  } else {
    context.copiedIds['ScoringJob'] = await fullCopyByParent(
      'ScoringJob',
      context.copiedIds['Item'] || [],
      'listScoringJobByItemId',
      'itemId',
      productionClient,
      sandboxClient,
      logger,
      config.tables['ScoringJob']
    );
  }

  if ((context.copiedIds['Item'] || []).length === 0) {
    logger.warn('ScoreResult', 'Skipping because no Item records were copied');
    context.copiedIds['ScoreResult'] = [];
  } else {
    context.copiedIds['ScoreResult'] = await fullCopyByParent(
      'ScoreResult',
      context.copiedIds['Item'] || [],
      'listScoreResultByItemId',
      'itemId',
      productionClient,
      sandboxClient,
      logger,
      config.tables['ScoreResult']
    );
  }

  if ((context.copiedIds['Item'] || []).length === 0) {
    logger.warn('FeedbackItem', 'Skipping because no Item records were copied');
    context.copiedIds['FeedbackItem'] = [];
  } else {
    context.copiedIds['FeedbackItem'] = await fullCopyByParent(
      'FeedbackItem',
      context.copiedIds['Item'] || [],
      'listFeedbackItemByItemId',
      'itemId',
      productionClient,
      sandboxClient,
      logger,
      config.tables['FeedbackItem']
    );
  }
}
