import type { SeedContext } from '../types';
import { fullCopy } from '../strategies/full-copy';

export async function seedPhase1(context: SeedContext): Promise<void> {
  const { sandboxClient, productionClient, accountId, config, logger } = context;

  logger.phase('Phase 1: Foundation Tables');

  // Account (independent)
  context.copiedIds['Account'] = await fullCopy(
    'Account',
    productionClient,
    sandboxClient,
    accountId,
    logger,
    config.tables['Account']
  );

  // User (independent)
  context.copiedIds['User'] = await fullCopy(
    'User',
    productionClient,
    sandboxClient,
    accountId,
    logger,
    config.tables['User']
  );
}
