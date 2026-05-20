import type { SeedContext } from '../types';
import { recentCopy } from '../strategies/recent-copy';
import { sampledCopy } from '../strategies/sampled-copy';
import { fullCopy } from '../strategies/full-copy';

export async function seedPhase5(context: SeedContext): Promise<void> {
  const { sandboxClient, productionClient, accountId, daysRecent, config, logger } = context;

  logger.phase('Phase 5: Derived & Linked Data');

  // Report and related
  await recentCopy(
    config.tables['Report'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  await recentCopy(
    config.tables['ChatSession'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  await recentCopy(
    config.tables['ChatMessage'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  await recentCopy(
    config.tables['AggregatedMetrics'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  // DataSet (recent)
  await recentCopy(
    config.tables['DataSet'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  // ReportBlock (depends on Report + DataSet)
  await recentCopy(
    config.tables['ReportBlock'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  // Identifier (linked to Item)
  await sampledCopy(
    config.tables['Identifier'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  // ScorecardExampleItem (links Scorecard + Item)
  await fullCopy('ScorecardExampleItem', productionClient, sandboxClient, accountId, logger);

  // TaskStage (linked to Task)
  await recentCopy(
    config.tables['TaskStage'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );
}
