import type { SeedContext } from '../types';
import { recentCopy } from '../strategies/recent-copy';
import { sampledCopy } from '../strategies/sampled-copy';
import { fullCopyByParent } from '../strategies/full-copy';

export async function seedPhase5(context: SeedContext): Promise<void> {
  const { sandboxClient, productionClient, accountId, daysRecent, config, logger } = context;

  logger.phase('Phase 5: Derived & Linked Data');

  // Report and related
  context.copiedIds['Report'] = await recentCopy(
    config.tables['Report'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  context.copiedIds['ChatSession'] = await recentCopy(
    config.tables['ChatSession'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  context.copiedIds['ChatMessage'] = await recentCopy(
    config.tables['ChatMessage'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  context.copiedIds['AggregatedMetrics'] = await recentCopy(
    config.tables['AggregatedMetrics'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  // DataSet (recent)
  context.copiedIds['DataSet'] = await recentCopy(
    config.tables['DataSet'],
    productionClient,
    sandboxClient,
    accountId,
    daysRecent,
    logger
  );

  // ReportBlock (depends on Report + DataSet)
  context.copiedIds['ReportBlock'] = await fullCopyByParent(
    'ReportBlock',
    context.copiedIds['Report'] || [],
    'listReportBlockByReportIdAndPosition',
    'reportId',
    productionClient,
    sandboxClient,
    logger,
    config.tables['ReportBlock']
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
  context.copiedIds['ScorecardExampleItem'] = await fullCopyByParent(
    'ScorecardExampleItem',
    context.copiedIds['Scorecard'] || [],
    'listScorecardExampleItemByScorecardIdAndAddedAt',
    'scorecardId',
    productionClient,
    sandboxClient,
    logger,
    {
      ...config.tables['ScorecardExampleItem'],
      queryArgs: { sortDirection: 'DESC' }
    }
  );

  // TaskStage (linked to Task)
  context.copiedIds['TaskStage'] = await fullCopyByParent(
    'TaskStage',
    context.copiedIds['Task'] || [],
    'listTaskStageByTaskId',
    'taskId',
    productionClient,
    sandboxClient,
    logger,
    config.tables['TaskStage']
  );
}
