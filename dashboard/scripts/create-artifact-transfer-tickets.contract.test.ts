import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const dashboardDir = resolve(__dirname, '..');
const repoRoot = resolve(dashboardDir, '..');
const dataResource = readFileSync(resolve(dashboardDir, 'amplify/data/resource.ts'), 'utf8');
const backend = readFileSync(resolve(dashboardDir, 'amplify/backend.ts'), 'utf8');
const manifest = JSON.parse(readFileSync(
  resolve(repoRoot, 'services/private-graphql-proxy/schema/amplify-manifest.json'),
  'utf8',
));

describe('artifact transfer ticket schema and infrastructure contract', () => {
  it('publishes a typed mutation for both Cognito and IAM identities, never an API key', () => {
    expect(manifest.customOperations.createArtifactTransferTickets).toMatchObject({
      operationType: 'mutation',
      arguments: {
        requests: {
          type: 'ArtifactTransferRequest',
          kind: 'ref',
          isArray: true,
          isRequired: true,
        },
      },
      returnType: 'ArtifactTransferTicket',
      returnIsArray: true,
      returnIsRequired: true,
    });
    expect(manifest.customTypes.ArtifactTransferRequest.fields).toMatchObject({
      operation: { type: 'string', kind: 'scalar', isRequired: true },
      resourceType: { type: 'string', kind: 'scalar', isRequired: true },
      artifactType: { type: 'string', kind: 'scalar', isRequired: true },
    });
    expect(manifest.authRules.createArtifactTransferTickets).toEqual(['authenticated', 'iam']);
    expect(dataResource).toContain("allow.authenticated('identityPool')");
  });

  it('limits the signing function to GetItem and the canonical bucket prefixes', () => {
    expect(backend).toContain("actions: ['dynamodb:GetItem']");
    expect(backend).toContain("actions: ['s3:GetObject', 's3:PutObject']");
    for (const prefix of ['datasets/*', 'procedures/*', 'reportblocks/procedures/*', 'scoreresults/*', 'evaluations/*', 'tasks/*']) {
      expect(backend).toContain(`'${prefix}'`);
    }
    expect(backend).toContain("tableEnvironmentName: 'EVALUATION_TABLE_NAME'");
  });
});
