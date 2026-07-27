import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { loadConsoleWorkerEnv } from './console-worker-env';

describe('loadConsoleWorkerEnv', () => {
  it('uses the generated dashboard data endpoint for a local Console worker', () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'console-worker-env-'));
    const outputsPath = path.join(tempDir, 'amplify_outputs.json');
    fs.writeFileSync(outputsPath, JSON.stringify({
      data: {
        url: 'https://sandbox.example.test/graphql',
        api_key: 'sandbox-api-key',
      },
    }));

    expect(loadConsoleWorkerEnv(outputsPath)).toEqual({
      PLEXUS_API_URL: 'https://sandbox.example.test/graphql',
      PLEXUS_API_KEY: 'sandbox-api-key',
    });
  });

  it('does not override the configured backend when generated outputs are absent', () => {
    expect(loadConsoleWorkerEnv('/does/not/exist/amplify_outputs.json')).toBeUndefined();
  });
});
