import { App, Stack } from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { SandboxCommandWorkerStack } from './sandbox-resource';
import { LIFECYCLE_APPSYNC_ROOTS, WORKER_APPSYNC_AUTHORITY_GROUPS, WORKER_DOMAIN_APPSYNC_ROOTS, appSyncFieldArn } from './authority-manifest';

function createStack(configSecretName?: string): SandboxCommandWorkerStack {
  const app = new App();
  const data = new Stack(app, 'Data');
  const taskTable = new dynamodb.Table(data, 'Task', { partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING }, stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES });
  const dataSourcesBucket = new s3.Bucket(data, 'DataSources');
  const reportBlockDetailsBucket = new s3.Bucket(data, 'ReportBlockDetails');
  const scoreResultAttachmentsBucket = new s3.Bucket(data, 'ScoreResultAttachments');
  return new SandboxCommandWorkerStack(data, 'SandboxCommandWorker', {
    taskTable,
    taskTableStreamArn: taskTable.tableStreamArn!,
    apiUrl: 'https://example.appsync-api.us-east-1.amazonaws.com/graphql',
    apiGraphqlArn: 'arn:aws:appsync:us-east-1:123456789012:apis/example',
    bedrockModelResources: ['arn:aws:bedrock:us-east-1::foundation-model/*'],
    configSecretName,
    dataSourcesBucket,
    reportBlockDetailsBucket,
    scoreResultAttachmentsBucket,
  });
}

describe('SandboxCommandWorkerStack', () => {
  it('is a nested child of the data stack that owns the Task table', () => {
    const app = new App();
    const data = new Stack(app, 'Data');
    const taskTable = new dynamodb.Table(data, 'Task', {
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      stream: dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
    });
    const dataSourcesBucket = new s3.Bucket(data, 'DataSources');
    const reportBlockDetailsBucket = new s3.Bucket(data, 'ReportBlockDetails');
    const scoreResultAttachmentsBucket = new s3.Bucket(data, 'ScoreResultAttachments');
    const sandbox = new SandboxCommandWorkerStack(data, 'SandboxCommandWorker', {
      taskTable,
      taskTableStreamArn: taskTable.tableStreamArn!,
      apiUrl: 'https://example.appsync-api.us-east-1.amazonaws.com/graphql',
      apiGraphqlArn: 'arn:aws:appsync:us-east-1:123456789012:apis/example',
      bedrockModelResources: ['arn:aws:bedrock:us-east-1::foundation-model/*'],
      dataSourcesBucket,
      reportBlockDetailsBucket,
      scoreResultAttachmentsBucket,
    });

    expect(sandbox.node.scope).toBe(data);
    expect(Object.values(Template.fromStack(data).findResources('AWS::CloudFormation::Stack')))
      .toHaveLength(1);
  });

  it('refuses a production config secret', () => {
    expect(() => createStack('plexus/production/config')).toThrow('must not use plexus/production/config');
  });

  it('defaults to the staging config secret', () => {
    const template = Template.fromStack(createStack());
    const rendered = JSON.stringify(template.toJSON());
    expect(rendered).toContain('plexus/staging/config');
  });

  it('borrows the staging foundation VPC contract, not a sandbox-specific one', () => {
    const rendered = JSON.stringify(Template.fromStack(createStack()).toJSON());
    expect(rendered).toContain('/plexus/staging/command-service/vpc-id');
    expect(rendered).toContain('/plexus/staging/command-service/availability-zones');
    expect(rendered).toContain('/plexus/staging/command-service/private-subnet-ids');
  });

  it('builds the worker image from a Docker asset rather than an ECR digest parameter', () => {
    const rendered = JSON.stringify(Template.fromStack(createStack()).toJSON());
    expect(rendered).not.toContain('worker-image-repository-arn');
    expect(rendered).not.toContain('current-worker-image-uri');
  });

  it('composes the queue, dispatcher, and a single Fargate worker service', () => {
    const template = Template.fromStack(createStack());
    expect(Object.keys(template.findResources('AWS::SQS::Queue'))).toHaveLength(3);
    template.resourceCountIs('AWS::ECS::Service', 1);
    template.resourceCountIs('AWS::Lambda::EventSourceMapping', 1);
  });

  it('uses shorter lease/heartbeat/visibility defaults than the long-lived service', () => {
    const template = Template.fromStack(createStack());
    template.hasResourceProperties('AWS::SQS::Queue', { VisibilityTimeout: 600 });
    const rendered = JSON.stringify(template.toJSON());
    expect(rendered).toContain('{"Name":"COMMAND_WORKER_LEASE_SECONDS","Value":"300"}');
    expect(rendered).toContain('{"Name":"COMMAND_WORKER_HEARTBEAT_SECONDS","Value":"60"}');
    expect(rendered).toContain('{"Name":"COMMAND_WORKER_VISIBILITY_TIMEOUT_SECONDS","Value":"600"}');
  });

  it('grants the six lifecycle roots plus the audited action-specific roots, same as the long-lived service', () => {
    const template = Template.fromStack(createStack());
    const statements = [
      ...Object.values(template.findResources('AWS::IAM::Policy')),
      ...Object.values(template.findResources('AWS::IAM::ManagedPolicy')),
    ]
      .flatMap((policy: any) => policy.Properties.PolicyDocument.Statement)
      .filter((statement: any) => statement.Action === 'appsync:GraphQL');

    expect(statements).toHaveLength(WORKER_APPSYNC_AUTHORITY_GROUPS.length);
    expect([...new Set(statements.flatMap((statement: any) => statement.Resource))].sort()).toEqual([
      ...LIFECYCLE_APPSYNC_ROOTS,
      ...WORKER_DOMAIN_APPSYNC_ROOTS,
    ].map((root) => appSyncFieldArn('arn:aws:appsync:us-east-1:123456789012:apis/example', root)).sort());
  });

  it('does not deploy the activity-gate IAM policy, since there is nothing to protect in an ephemeral sandbox', () => {
    const rendered = JSON.stringify(Template.fromStack(createStack()).toJSON());
    expect(rendered).not.toContain('command-task-activity-gate');
  });
});
