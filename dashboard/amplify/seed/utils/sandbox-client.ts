import { generateClient } from 'aws-amplify/data';
import type { Schema } from '../../data/resource';

/**
 * Creates a client for the sandbox environment using the configured,
 * signed-in Amplify singleton.
 */
export function createSandboxClient() {
  return generateClient<Schema>();
}
