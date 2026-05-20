import type { SeedContext } from '../types';
import { fullCopy } from '../strategies/full-copy';

export async function seedPhase1(context: SeedContext): Promise<void> {
  const { sandboxClient, productionClient, accountId, logger } = context;

  logger.phase('Phase 1: Foundation Tables');

  // Account (independent)
  await fullCopy('Account', productionClient, sandboxClient, accountId, logger);

  // User (independent)
  await fullCopy('User', productionClient, sandboxClient, accountId, logger);
}
