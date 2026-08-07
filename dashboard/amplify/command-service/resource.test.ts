import { App, Stack } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { readFileSync } from 'fs';
import * as path from 'path';
import { CommandService, isLongLivedCommandServiceEnvironment, resolveCommandServiceEnvironment } from './resource';
import { TaskDispatcherStack, TaskStreamDispatcher } from '../functions/taskDispatcher/resource';
import { LIFECYCLE_APPSYNC_ROOTS, WORKER_DOMAIN_APPSYNC_ROOTS, appSyncFieldArn } from './authority-manifest';

const DIGEST = `123456789012.dkr.ecr.us-east-1.amazonaws.com/plexus-staging-command-worker@sha256:${'a'.repeat(64)}`;
const DEPLOYMENT_ROLE_ARN = 'arn:aws:iam::123456789012:role/amplify-deployment';

type CommandServiceFixture = {
  app: App;
  data: Stack;
  storage: Stack;
  service: CommandService;
};

function createFixture(workerImageUri = DIGEST): CommandServiceFixture {
  const app = new App();
  const data = new Stack(app, 'Data');
  const storage = new Stack(app, 'Storage');
  const taskTable = new dynamodb.Table(data, 'Task', { partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING }, stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES });
  const dataSourcesBucket = new s3.Bucket(storage, 'DataSources');
  const reportBlockDetailsBucket = new s3.Bucket(storage, 'ReportBlockDetails');
  const scoreResultAttachmentsBucket = new s3.Bucket(storage, 'ScoreResultAttachments');
  const service = new CommandService(data, 'CommandService', {
    taskTable,
    taskTableStreamArn: taskTable.tableStreamArn!,
    apiUrl: 'https://example.appsync-api.us-east-1.amazonaws.com/graphql',
    apiGraphqlArn: 'arn:aws:appsync:us-east-1:123456789012:apis/example',
    workerImageUri,
    foundationRepositoryUri: '123456789012.dkr.ecr.us-east-1.amazonaws.com/plexus-staging-command-worker',
    configSecretName: 'plexus/staging/config',
    bedrockModelResources: ['arn:aws:bedrock:us-east-1::foundation-model/*'],
    environmentName: 'staging',
    amplifyDeploymentRoleArn: DEPLOYMENT_ROLE_ARN,
    dataSourcesBucket,
    reportBlockDetailsBucket,
    scoreResultAttachmentsBucket,
  });
  return { app, data, storage, service };
}

function createStack(workerImageUri = DIGEST): Stack {
  return createFixture(workerImageUri).data;
}

function createSandboxDispatcherStack(): TaskDispatcherStack {
  const app = new App();
  const data = new Stack(app, 'Data');
  const taskTable = new dynamodb.Table(data, 'Task', {
    partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
    stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
  });
  return new TaskDispatcherStack(app, 'SandboxTaskDispatcher', {
    taskTable,
    taskTableStreamArn: taskTable.tableStreamArn!,
  });
}

describe('CommandService', () => {
  it.each([['main', 'production'], ['production', 'production'], ['staging', 'staging']])('maps %s to %s', (source, expected) => {
    expect(resolveCommandServiceEnvironment(source)).toBe(expected);
  });

  it.each(['sandbox', 'development', 'feature/test'])('rejects non-long-lived environment %s', (environment) => {
    expect(() => resolveCommandServiceEnvironment(environment)).toThrow('sandboxes have no ECS network');
  });

  it.each([
    ['production', true], ['staging', true], ['development', false], ['sandbox', false],
  ])('gates backend command-service composition for %s', (environment, expected) => {
    expect(isLongLivedCommandServiceEnvironment(environment)).toBe(expected);
  });

  it('keeps the legacy dispatcher sandbox-explicit and separate from the command service', () => {
    const backend = readFileSync(path.join(process.cwd(), 'amplify/backend.ts'), 'utf8');
    expect(backend).toContain('if (isSandbox && enableSandboxTaskDispatcher)');
    expect(backend).toContain('if (isLongLivedCommandServiceEnvironment(commandServiceEnvironment))');
    expect(backend).not.toContain('if (!isSandbox || enableSandboxTaskDispatcher)');
  });

  it('preserves legacy Task dispatcher exports during the two-deployment migration', () => {
    const backend = readFileSync(path.join(process.cwd(), 'amplify/backend.ts'), 'utf8');
    expect(backend).toContain('backend.stack.exportValue(taskTable.tableArn)');
    expect(backend).toContain('backend.stack.exportValue(taskTable.tableStreamArn)');
    expect(backend).not.toContain('backend.data.stack.exportValue(taskTable.');
  });

  it('is a Data-owned construct with only a Data-to-Storage stack dependency', () => {
    const { app, data, storage, service } = createFixture();
    const backend = readFileSync(path.join(process.cwd(), 'amplify/backend.ts'), 'utf8');
    app.synth();

    expect(service).not.toBeInstanceOf(Stack);
    expect(Stack.of(service)).toBe(data);
    expect(data.dependencies).toContain(storage);
    expect(storage.dependencies).not.toContain(data);
    expect(backend).toMatch(/new CommandService\(\s*backend\.data\.stack/);
    expect(backend).not.toContain("backend.createStack('CommandServiceStack')");
  });

  it('composes separate command and dispatcher recovery queues with an ECS worker', () => {
    const template = Template.fromStack(createStack());
    expect(Object.keys(template.findResources('AWS::SQS::Queue'))).toHaveLength(3);
    template.resourceCountIs('AWS::ECS::Service', 1);
    template.hasResourceProperties('AWS::ECS::Service', { DeploymentConfiguration: { MinimumHealthyPercent: 100, MaximumPercent: 200 } });
    template.resourceCountIs('AWS::Lambda::EventSourceMapping', 1);
    template.hasResourceProperties('AWS::SQS::Queue', { VisibilityTimeout: 43200 });
    template.hasResourceProperties('AWS::CloudWatch::Alarm', { MetricName: 'RunningTaskCount', Namespace: 'ECS/ContainerInsights' });
    const policies = Object.values(template.findResources('AWS::IAM::Policy'));
    expect(policies.some((policy) => JSON.stringify(policy).includes('ecs:UpdateTaskProtection'))).toBe(true);
  });

  it('grants the six lifecycle roots plus the audited action-specific roots', () => {
    const template = Template.fromStack(createStack());
    const statements = Object.values(template.findResources('AWS::IAM::Policy'))
      .flatMap((policy: any) => policy.Properties.PolicyDocument.Statement)
      .filter((statement: any) => statement.Action === 'appsync:GraphQL');

    expect(statements).toHaveLength(1);
    expect([...statements[0].Resource].sort()).toEqual([
      ...LIFECYCLE_APPSYNC_ROOTS,
      ...WORKER_DOMAIN_APPSYNC_ROOTS,
    ].map((root) => appSyncFieldArn('arn:aws:appsync:us-east-1:123456789012:apis/example', root)).sort());
    expect(statements[0].Resource.every((resource: string) => !resource.includes('*'))).toBe(true);
  });

  it('scopes direct worker storage access to audited object prefixes and exports bucket identities', () => {
    const template = Template.fromStack(createStack());
    const rendered = JSON.stringify(template.toJSON());
    const s3Statements = Object.values(template.findResources('AWS::IAM::Policy'))
      .flatMap((policy: any) => policy.Properties.PolicyDocument.Statement)
      .filter((statement: any) => {
        const actions = Array.isArray(statement.Action) ? statement.Action : [statement.Action]
        return actions.some((action: string) => action.startsWith('s3:'))
      })

    for (const prefix of ['datasets/*', 'datasources/*', 'procedures/*', 'reportblocks/*', 'scoreresults/*', 'evaluations/*']) {
      expect(rendered).toContain(prefix)
    }
    expect(rendered).toContain('AMPLIFY_STORAGE_DATASETS_BUCKET_NAME')
    expect(rendered).toContain('AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME')
    expect(rendered).toContain('AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME')
    expect(s3Statements).toHaveLength(2)
    expect(s3Statements.flatMap((statement: any) => Array.isArray(statement.Resource) ? statement.Resource : [statement.Resource]))
      .not.toContain('*')
  });

  it('grants the deployment identity only Scan on the authoritative Task table', () => {
    const template = Template.fromStack(createStack());
    const statements = Object.values(template.findResources('AWS::IAM::Policy'))
      .filter((policy: any) => policy.Properties.Roles?.includes('amplify-deployment'))
      .flatMap((policy: any) => policy.Properties.PolicyDocument.Statement);

    expect(statements).toEqual([{
      Action: 'dynamodb:Scan',
      Effect: 'Allow',
      Resource: { 'Fn::GetAtt': [expect.stringMatching(/Task/), 'Arn'] },
    }]);
  });

  it('uses one TaskStreamDispatcher composition for both command-service and sandbox stacks', () => {
    const commandService = createStack();
    const sandboxDispatcher = createSandboxDispatcherStack();

    expect(commandService.node.findAll().filter((node) => node instanceof TaskStreamDispatcher)).toHaveLength(1);
    expect(sandboxDispatcher.node.findAll().filter((node) => node instanceof TaskStreamDispatcher)).toHaveLength(1);

    for (const stack of [commandService, sandboxDispatcher]) {
      const template = Template.fromStack(stack);
      expect(Object.keys(template.findResources('AWS::SQS::Queue'))).toHaveLength(3);
      template.resourceCountIs('AWS::Lambda::EventSourceMapping', 1);
      template.hasResourceProperties('AWS::SQS::Queue', { VisibilityTimeout: 43200 });
    }
  });

  it.each(['latest', 'repository:tag', 'repository@sha256:not-a-digest'])('rejects mutable worker image %s', (image) => {
    expect(() => createStack(image)).toThrow('immutable repository@sha256 digest');
  });

  it('rejects an image digest from a repository other than the foundation repository', () => {
    const image = `123456789012.dkr.ecr.us-east-1.amazonaws.com/other@sha256:${'a'.repeat(64)}`;
    expect(() => createStack(image)).toThrow('must match the foundation repository URI');
  });
});
