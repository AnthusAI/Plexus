import { generateClient } from 'aws-amplify/data';
import type { Schema } from '../../data/resource';

/**
 * Creates a client for the sandbox environment.
 * The sandbox is automatically configured by Amplify when the seed script runs.
 */
export function createSandboxClient() {
  return generateClient<Schema>();
}
