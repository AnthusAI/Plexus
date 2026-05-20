import type { SeedContext } from '../types';
import { recentCopy } from '../strategies/recent-copy';
import { sampledCopy } from '../strategies/sampled-copy';

export async function seedPhase4(context: SeedContext): Promise<void> {
  const { sandboxClient, productionClient, accountId, daysRecent, config, logger } = context;

  logger.phase('Phase 4: Operational & Large-Scale Data');

  // Operational tables (recent data only)
  await recentCopy(
    config.tables['Task'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  await recentCopy(
    config.tables['Evaluation'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  // Large-scale tables (sampled)
  await sampledCopy(
    config.tables['Item'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  await sampledCopy(
    config.tables['ScoringJob'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  await sampledCopy(
    config.tables['ScoreResult'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  await sampledCopy(
    config.tables['FeedbackItem'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );
}
