import { createHash } from 'node:crypto';
import { appendFileSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { getSecret, createAndSignUpUser, signInUser } from '@aws-amplify/seed';
import { Amplify } from 'aws-amplify';
import { loadConfig } from './config';
import { Logger } from './utils/logger';
import { createProductionClient } from './utils/production-client';
import { createSandboxClient } from './utils/sandbox-client';
import {
  listVisibleAccounts,
  resolveAccountById,
  resolveAccountByKey
} from './utils/model-queries';
import { syncStorageBuckets } from './utils/storage-sync';
import { seedPhase1 } from './phases/phase1-foundation';
import { seedPhase2 } from './phases/phase2-structure';
import { seedPhase3 } from './phases/phase3-reference';
import { seedPhase4 } from './phases/phase4-operational';
import { seedPhase5 } from './phases/phase5-derived';

const logger = new Logger();

async function getTrimmedSecret(name: string): Promise<string> {
  return (await getSecret(name) || '').trim();
}

function getSeedUsername(password: string): string {
  const passwordHash = createHash('sha256').update(password).digest('hex').slice(0, 12);
  return `sandbox-seed-${passwordHash}@plexus.internal`;
}

export default async function seed() {
  // Write to file to verify execution
  const logPath = '/tmp/plexus-seed-debug.log';
  const log = (msg: string) => {
    appendFileSync(logPath, `${new Date().toISOString()} - ${msg}\n`);
  };

  log('========================================');
  log('SEED SCRIPT STARTED');
  log('========================================');

  // Force output to be visible
  console.error('========================================');
  console.error('🌱 SEED SCRIPT STARTED');
  console.error('========================================');

  logger.start('Plexus Sandbox Seeding');

  try {
    log('Loading configuration...');
    const outputsUrl = new URL('../../amplify_outputs.json', import.meta.url);
    const outputs = JSON.parse(await readFile(outputsUrl, { encoding: 'utf8' }));
    Amplify.configure(outputs);
    logger.info('Config', 'Configured Amplify from amplify_outputs.json');

    // Load configuration
    const config = await loadConfig();
    log(`Config loaded: ${Object.keys(config.tables).length} tables`);
    logger.info('Config', `Loaded configuration for ${Object.keys(config.tables).length} tables`);

    // Get production credentials from secrets
    const prodApiUrl = await getTrimmedSecret('PROD_API_URL');
    const prodApiKey = await getTrimmedSecret('PROD_API_KEY');
    const configuredAccountId = await getTrimmedSecret('PROD_ACCOUNT_ID');
    const configuredAccountKey = await getTrimmedSecret('PROD_ACCOUNT_KEY');
    const includeS3 = (await getTrimmedSecret('INCLUDE_S3_SYNC')).toLowerCase() === 'true';
    const daysRecent = parseInt(await getTrimmedSecret('DAYS_RECENT') || '30');
    const seedUserPassword = await getTrimmedSecret('SEED_USER_PASSWORD');
    const seedUsername = getSeedUsername(seedUserPassword);

    logger.info('Secrets', `Configured account key: ${configuredAccountKey || '(not set)'}`);
    logger.info('Secrets', `Configured account ID: ${configuredAccountId ? `${configuredAccountId.substring(0, 8)}...` : '(not set)'}`);
    logger.info('Secrets', `Days of recent data: ${daysRecent}`);
    logger.info('Secrets', `S3 sync enabled: ${includeS3}`);

    // Create/sign in seed user in sandbox
    logger.phase('Creating seed user');
    try {
      const user = await createAndSignUpUser({
        username: seedUsername,
        password: seedUserPassword,
        signInAfterCreation: true,
        signInFlow: 'Password'
      });
      logger.info('Auth', 'Seed user created and signed in');
    } catch (error: any) {
      if (error.name === 'UsernameExistsError') {
        await signInUser({
          username: seedUsername,
          password: seedUserPassword,
          signInFlow: 'Password'
        });
        logger.info('Auth', 'Existing seed user signed in');
      } else {
        throw error;
      }
    }

    // Initialize clients
    const sandboxClient = createSandboxClient();
    const productionClient = createProductionClient(prodApiUrl, prodApiKey, outputs);
    logger.info('Clients', 'Production and sandbox clients initialized');

    const accountByKey = configuredAccountKey
      ? await resolveAccountByKey(productionClient, configuredAccountKey)
      : null;
    const accountById = configuredAccountId
      ? await resolveAccountById(productionClient, configuredAccountId)
      : null;
    const resolvedAccount = accountByKey || accountById;

    if (!resolvedAccount) {
      const visibleAccounts = await listVisibleAccounts(productionClient);
      const visibleSummary = visibleAccounts.length > 0
        ? visibleAccounts.map((account) => `${account.id}${account.key ? ` (${account.key})` : ''}`).join(', ')
        : 'none';

      throw new Error(
        [
          'Could not resolve production account.',
          configuredAccountKey ? `Configured key: ${configuredAccountKey}.` : 'No PROD_ACCOUNT_KEY configured.',
          configuredAccountId ? `Configured ID: ${configuredAccountId}.` : 'No PROD_ACCOUNT_ID configured.',
          `Visible accounts: ${visibleSummary}.`
        ].join(' ')
      );
    }

    if (configuredAccountId && configuredAccountId !== resolvedAccount.id) {
      logger.warn(
        'Secrets',
        `Configured PROD_ACCOUNT_ID ${configuredAccountId} does not match account key ${resolvedAccount.key || configuredAccountKey}; using ${resolvedAccount.id}`
      );
    }
    logger.info('Secrets', `Resolved account: ${resolvedAccount.id}${resolvedAccount.key ? ` (${resolvedAccount.key})` : ''}`);

    // Context for all phases
    const context = {
      sandboxClient,
      productionClient,
      accountId: resolvedAccount.id,
      daysRecent,
      config,
      logger,
      copiedIds: {}
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

    log('========================================');
    log('SEED COMPLETED SUCCESSFULLY');
    log('========================================');
    logger.complete('Sandbox seeding completed successfully!');
  } catch (error: any) {
    log('========================================');
    log('ERROR: ' + error.message);
    log('Stack: ' + error.stack);
    log('========================================');
    console.error('========================================');
    console.error('❌ SEED SCRIPT ERROR');
    console.error('========================================');
    logger.error('Seed', `Fatal error: ${error.message}`);
    console.error('Full error:', error);
    console.error('Stack:', error.stack);
    throw error;
  }
}

await seed();
