import type { SeedContext } from '../types';
import { fullCopy, fullCopyByParent } from '../strategies/full-copy';

export async function seedPhase3(context: SeedContext): Promise<void> {
  const { sandboxClient, productionClient, accountId, config, logger } = context;

  logger.phase('Phase 3: Reference Data');

  // These can potentially run in parallel, but we'll run sequentially for simplicity
  // ReportConfiguration (references Account)
  context.copiedIds['ReportConfiguration'] = await fullCopy(
    'ReportConfiguration',
    productionClient,
    sandboxClient,
    accountId,
    logger,
    config.tables['ReportConfiguration']
  );

  // ShareLink (references Account)
  context.copiedIds['ShareLink'] = await fullCopy(
    'ShareLink',
    productionClient,
    sandboxClient,
    accountId,
    logger,
    config.tables['ShareLink']
  );

  // DataSource (references Account + Scorecard + Score)
  context.copiedIds['DataSource'] = await fullCopy(
    'DataSource',
    productionClient,
    sandboxClient,
    accountId,
    logger,
    config.tables['DataSource']
  );

  // DataSourceVersion (references DataSource)
  context.copiedIds['DataSourceVersion'] = await fullCopyByParent(
    'DataSourceVersion',
    context.copiedIds['DataSource'] || [],
    'listDataSourceVersionByDataSourceIdAndCreatedAt',
    'dataSourceId',
    productionClient,
    sandboxClient,
    logger,
    {
      ...config.tables['DataSourceVersion'],
      queryArgs: { sortDirection: 'DESC' }
    }
  );

  // Procedure (references Account + Scorecard + Score + ScoreVersion)
  context.copiedIds['Procedure'] = await fullCopy(
    'Procedure',
    productionClient,
    sandboxClient,
    accountId,
    logger,
    config.tables['Procedure']
  );
}
