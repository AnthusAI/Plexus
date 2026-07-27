const fs = require('node:fs');
const path = require('node:path');

/**
 * The browser configures Amplify from the generated outputs file.  A local
 * Console worker must use the same data endpoint or it will poll a different
 * backend and never see browser-created messages.
 */
function loadConsoleWorkerEnv(outputsPath = path.resolve(__dirname, '..', 'amplify_outputs.json')) {
  if (!fs.existsSync(outputsPath)) return undefined;

  const parsed = JSON.parse(fs.readFileSync(outputsPath, 'utf8'));
  const url = typeof parsed?.data?.url === 'string' ? parsed.data.url.trim() : '';
  const apiKey = typeof parsed?.data?.api_key === 'string' ? parsed.data.api_key.trim() : '';
  if (!url || !apiKey) return undefined;

  return {
    PLEXUS_API_URL: url,
    PLEXUS_API_KEY: apiKey,
  };
}

function shellQuote(value) {
  return `'${value.replace(/'/g, `'\\"'\\"'`)}'`;
}

if (require.main === module) {
  const env = loadConsoleWorkerEnv(process.argv[2]);
  if (env) {
    for (const [name, value] of Object.entries(env)) {
      process.stdout.write(`export ${name}=${shellQuote(value)}\n`);
    }
  }
}

module.exports = { loadConsoleWorkerEnv };
