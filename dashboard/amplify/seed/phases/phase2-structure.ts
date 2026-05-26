import type { SeedContext } from '../types';
import { fullCopy, fullCopyByParent } from '../strategies/full-copy';

export async function seedPhase2(context: SeedContext): Promise<void> {
  const { sandboxClient, productionClient, accountId, config, logger } = context;

  logger.phase('Phase 2: Core Structure (Scorecard Hierarchy)');

  // Scorecard (references Account)
  context.copiedIds['Scorecard'] = await fullCopy(
    'Scorecard',
    productionClient,
    sandboxClient,
    accountId,
    logger,
    config.tables['Scorecard']
  );

  // ScorecardSection (references Scorecard)
  context.copiedIds['ScorecardSection'] = await fullCopyByParent(
    'ScorecardSection',
    context.copiedIds['Scorecard'] || [],
    'listScorecardSectionByScorecardId',
    'scorecardId',
    productionClient,
    sandboxClient,
    logger,
    config.tables['ScorecardSection']
  );

  // Score (references ScorecardSection + Scorecard)
  context.copiedIds['Score'] = await fullCopyByParent(
    'Score',
    context.copiedIds['Scorecard'] || [],
    'listScoreByScorecardIdAndExternalId',
    'scorecardId',
    productionClient,
    sandboxClient,
    logger,
    config.tables['Score']
  );

  // ScoreVersion (references Score + User)
  context.copiedIds['ScoreVersion'] = await fullCopyByParent(
    'ScoreVersion',
    context.copiedIds['Score'] || [],
    'listScoreVersionByScoreIdAndCreatedAt',
    'scoreId',
    productionClient,
    sandboxClient,
    logger,
    {
      ...config.tables['ScoreVersion'],
      queryArgs: { sortDirection: 'DESC' }
    }
  );
}
