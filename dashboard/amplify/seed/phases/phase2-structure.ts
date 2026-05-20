import type { SeedContext } from '../types';
import { fullCopy } from '../strategies/full-copy';

export async function seedPhase2(context: SeedContext): Promise<void> {
  const { sandboxClient, productionClient, accountId, logger } = context;

  logger.phase('Phase 2: Core Structure (Scorecard Hierarchy)');

  // Scorecard (references Account)
  await fullCopy('Scorecard', productionClient, sandboxClient, accountId, logger);

  // ScorecardSection (references Scorecard)
  await fullCopy('ScorecardSection', productionClient, sandboxClient, accountId, logger);

  // Score (references ScorecardSection + Scorecard)
  await fullCopy('Score', productionClient, sandboxClient, accountId, logger);

  // ScoreVersion (references Score + User)
  await fullCopy('ScoreVersion', productionClient, sandboxClient, accountId, logger);
}
