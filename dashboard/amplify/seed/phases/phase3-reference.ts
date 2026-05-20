import type { SeedContext } from '../types';
import { fullCopy } from '../strategies/full-copy';

export async function seedPhase3(context: SeedContext): Promise<void> {
  const { sandboxClient, productionClient, accountId, logger } = context;

  logger.phase('Phase 3: Reference Data');

  // These can potentially run in parallel, but we'll run sequentially for simplicity
  // ReportConfiguration (references Account)
  await fullCopy('ReportConfiguration', productionClient, sandboxClient, accountId, logger);

  // ShareLink (references Account)
  await fullCopy('ShareLink', productionClient, sandboxClient, accountId, logger);

  // DataSource (references Account + Scorecard + Score)
  await fullCopy('DataSource', productionClient, sandboxClient, accountId, logger);

  // DataSourceVersion (references DataSource)
  await fullCopy('DataSourceVersion', productionClient, sandboxClient, accountId, logger);

  // Procedure (references Account + Scorecard + Score + ScoreVersion)
  await fullCopy('Procedure', productionClient, sandboxClient, accountId, logger);
}
