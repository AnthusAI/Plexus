import { getSecret, createAndSignUpUser, signInUser } from '@aws-amplify/seed';
import { loadConfig } from './config';
import { Logger } from './utils/logger';
import { createProductionClient } from './utils/production-client';
import { createSandboxClient } from './utils/sandbox-client';
import { syncStorageBuckets } from './utils/storage-sync';
import { seedPhase1 } from './phases/phase1-foundation';
import { seedPhase2 } from './phases/phase2-structure';
import { seedPhase3 } from './phases/phase3-reference';
import { seedPhase4 } from './phases/phase4-operational';
import { seedPhase5 } from './phases/phase5-derived';

const logger = new Logger();

export default async function seed() {
  logger.start('Plexus Sandbox Seeding');

  try {
    // Load configuration
    const config = await loadConfig();
    logger.info('Config', `Loaded configuration for ${Object.keys(config.tables).length} tables`);

    // Get production credentials from secrets
    const prodApiUrl = await getSecret('PROD_API_URL');
    const prodApiKey = await getSecret('PROD_API_KEY');
    const accountId = await getSecret('PROD_ACCOUNT_ID');
    const includeS3 = (await getSecret('INCLUDE_S3_SYNC'))?.toLowerCase() === 'true';
    const daysRecent = parseInt(await getSecret('DAYS_RECENT') || '30');

    logger.info('Secrets', `Using account ID: ${accountId?.substring(0, 8)}...`);
    logger.info('Secrets', `Days of recent data: ${daysRecent}`);
    logger.info('Secrets', `S3 sync enabled: ${includeS3}`);

    // Create/sign in seed user in sandbox
    logger.phase('Creating seed user');
    try {
      const user = await createAndSignUpUser({
        username: 'sandbox-seed@plexus.internal',
        password: await getSecret('SEED_USER_PASSWORD'),
        signInAfterCreation: true,
        signInFlow: 'Password'
      });
      logger.info('Auth', 'Seed user created and signed in');
    } catch (error: any) {
      if (error.name === 'UsernameExistsError') {
        await signInUser({
          username: 'sandbox-seed@plexus.internal',
          password: await getSecret('SEED_USER_PASSWORD')
        });
        logger.info('Auth', 'Existing seed user signed in');
      } else {
        throw error;
      }
    }

    // Initialize clients
    const sandboxClient = createSandboxClient();
    const productionClient = createProductionClient(prodApiUrl!, prodApiKey!);
    logger.info('Clients', 'Production and sandbox clients initialized');

    // Context for all phases
    const context = {
      sandboxClient,
      productionClient,
      accountId: accountId!,
      daysRecent,
      config,
      logger
    };

    // Execute seeding phases
    await seedPhase1(context);
    await seedPhase2(context);
    await seedPhase3(context);
    await seedPhase4(context);
    await seedPhase5(context);

    // Optional: S3 sync (disabled by default)
    if (includeS3) {
      logger.phase('S3 Storage Sync');
      await syncStorageBuckets(context);
    } else {
      logger.info('Config', 'Skipping S3 sync (default). Set INCLUDE_S3_SYNC=true to enable.');
    }

    logger.complete('Sandbox seeding completed successfully!');
  } catch (error: any) {
    logger.error('Seed', `Fatal error: ${error.message}`);
    console.error(error);
    throw error;
  }
}
