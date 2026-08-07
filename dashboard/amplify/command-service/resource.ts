import { CfnOutput, Duration, Fn, Stack } from 'aws-cdk-lib';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { Construct } from 'constructs';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { IBucket } from 'aws-cdk-lib/aws-s3';
import { TaskStreamDispatcher } from '../functions/taskDispatcher/resource';
import { WORKER_APPSYNC_AUTHORITY_GROUPS, appSyncFieldArn } from './authority-manifest';

const IMAGE_URI_PATTERN = /^.+@sha256:[a-f0-9]{64}$/;
const ENVIRONMENTS: Record<string, string> = {
  main: 'production',
  production: 'production',
  staging: 'staging',
};

export function resolveCommandServiceEnvironment(value: string): string {
  const resolved = ENVIRONMENTS[value.trim().toLowerCase()];
  if (!resolved) {
    throw new Error('Command service supports only main/production or staging; sandboxes have no ECS network');
  }
  return resolved;
}

export function isLongLivedCommandServiceEnvironment(value: string): boolean {
  return value === 'production' || value === 'staging';
}

export interface CommandServiceProps {
  readonly taskTable: ITable;
  readonly taskTableStreamArn: string;
  readonly apiUrl: string;
  readonly apiGraphqlArn: string;
  /** Required repository@sha256 digest selected by the deployment pipeline. */
  readonly workerImageUri: string;
  /** Repository URI read from the foundation during the image handoff. */
  readonly foundationRepositoryUri: string;
  readonly configSecretName: string;
  readonly bedrockModelResources: readonly string[];
  readonly servicePrefix?: string;
  readonly environmentName: string;
  /** Existing Amplify deployment identity that performs the pre-deploy gate. */
  readonly amplifyDeploymentRoleArn: string;
  readonly dataSourcesBucket: IBucket;
  readonly reportBlockDetailsBucket: IBucket;
  readonly scoreResultAttachmentsBucket: IBucket;
}

/**
 * Application resources for the Task-authoritative command service.
 *
 * Networking and the worker image repository belong to a separately deployed
 * foundation. This construct imports that contract into its owning Amplify stack.
 */
export class CommandService extends Construct {
  public readonly commandQueue: sqs.Queue;
  public readonly commandDeadLetterQueue: sqs.Queue;
  public readonly dispatcherFailureQueue: sqs.Queue;
  public readonly dispatcherFunction: lambda.Function;
  public readonly workerService: ecs.FargateService;

  constructor(scope: Construct, id: string, props: CommandServiceProps) {
    super(scope, id);
    const stack = Stack.of(this);
    const environment = resolveCommandServiceEnvironment(props.environmentName);
    const prefix = (props.servicePrefix || 'plexus').trim().toLowerCase();
    if (!prefix) {
      throw new Error('Command service prefix must not be empty');
    }
    if (!IMAGE_URI_PATTERN.test(props.workerImageUri)) {
      throw new Error('workerImageUri must be an immutable repository@sha256 digest');
    }
    const [imageRepositoryUri] = props.workerImageUri.split('@', 1);
    if (!props.foundationRepositoryUri.trim() || imageRepositoryUri !== props.foundationRepositoryUri) {
      throw new Error('workerImageUri repository must match the foundation repository URI');
    }
    if (!props.apiUrl.trim() || !props.apiGraphqlArn.trim()) {
      throw new Error('Command service requires an AppSync API URL and GraphQL ARN');
    }
    if (!props.configSecretName.trim()) {
      throw new Error('Command service requires a runtime config secret');
    }
    if (props.bedrockModelResources.length === 0) {
      throw new Error('Command service requires allowed Bedrock model resources');
    }
    if (!props.amplifyDeploymentRoleArn.trim()) {
      throw new Error('Command service requires the Amplify deployment role ARN');
    }

    const deploymentRole = iam.Role.fromRoleArn(
      this,
      'AmplifyDeploymentRole',
      props.amplifyDeploymentRoleArn,
      { mutable: false },
    );
    new iam.CfnPolicy(this, 'AmplifyTaskActivityGateAccess', {
      policyName: `${prefix}-${environment}-command-task-activity-gate`,
      roles: [deploymentRole.roleName],
      policyDocument: new iam.PolicyDocument({
        statements: [new iam.PolicyStatement({
          actions: ['dynamodb:Scan'],
          resources: [props.taskTable.tableArn],
        })],
      }),
    });

    const contractPrefix = `/${prefix}/${environment}/command-service`;
    const vpc = ec2.Vpc.fromVpcAttributes(this, 'CommandServiceVpc', {
      vpcId: ssm.StringParameter.valueForStringParameter(this, `${contractPrefix}/vpc-id`),
      availabilityZones: Fn.split(',', ssm.StringParameter.valueForStringParameter(this, `${contractPrefix}/availability-zones`)),
      privateSubnetIds: Fn.split(',', ssm.StringParameter.valueForStringParameter(this, `${contractPrefix}/private-subnet-ids`)),
    });
    const repositoryArn = ssm.StringParameter.valueForStringParameter(
      this,
      `${contractPrefix}/worker-image-repository-arn`,
    );
    const repository = ecr.Repository.fromRepositoryAttributes(this, 'CommandWorkerImageRepository', {
      repositoryArn,
      repositoryName: Fn.select(1, Fn.split('/', repositoryArn)),
    });
    const imageDigest = props.workerImageUri.slice(props.workerImageUri.lastIndexOf('@') + 1);

    const dispatcher = new TaskStreamDispatcher(this, 'TaskStreamDispatcher', {
      taskTable: props.taskTable,
      taskTableStreamArn: props.taskTableStreamArn,
    });
    this.commandQueue = dispatcher.commandQueue;
    this.commandDeadLetterQueue = dispatcher.commandDeadLetterQueue;
    this.dispatcherFailureQueue = dispatcher.dispatcherFailureQueue;
    this.dispatcherFunction = dispatcher.dispatcherFunction;
    const workerLogGroup = new logs.LogGroup(this, 'CommandWorkerLogGroup', {
      retention: environment === 'production' ? logs.RetentionDays.THREE_MONTHS : logs.RetentionDays.ONE_MONTH,
    });
    const cluster = new ecs.Cluster(this, 'CommandWorkerCluster', { vpc, containerInsightsV2: ecs.ContainerInsights.ENABLED });
    const securityGroup = new ec2.SecurityGroup(this, 'CommandWorkerSecurityGroup', {
      vpc,
      description: 'No-ingress command-worker security group',
      allowAllOutbound: false,
    });
    securityGroup.addEgressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(443), 'HTTPS to AWS and public providers');
    const taskRole = new iam.Role(this, 'CommandWorkerTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });
    const executionRole = new iam.Role(this, 'CommandWorkerExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy')],
    });
    this.commandQueue.grantConsumeMessages(taskRole);
    const runtimeConfigSecret = secretsmanager.Secret.fromSecretNameV2(
      this,
      'RuntimeConfigSecret',
      props.configSecretName,
    );
    // Keep exact field-level authority without one indivisible policy statement.
    // Direct action groups avoid inherited duplication and wildcard broadening.
    for (const group of WORKER_APPSYNC_AUTHORITY_GROUPS) {
      taskRole.addManagedPolicy(new iam.ManagedPolicy(this, `CommandWorker${group.id}AppSyncPolicy`, {
        description: `Command worker AppSync authority for ${group.source}`,
        statements: [new iam.PolicyStatement({
          actions: ['appsync:GraphQL'],
          resources: group.roots.map((root) => appSyncFieldArn(props.apiGraphqlArn, root)),
        })],
      }));
    }
    taskRole.addToPolicy(new iam.PolicyStatement({
      actions: ['s3:GetObject'],
      resources: [
        props.dataSourcesBucket.arnForObjects('datasets/*'),
        props.dataSourcesBucket.arnForObjects('datasources/*'),
      ],
    }));
    taskRole.addToPolicy(new iam.PolicyStatement({
      actions: ['s3:GetObject', 's3:PutObject'],
      resources: [
        props.reportBlockDetailsBucket.arnForObjects('procedures/*'),
        props.reportBlockDetailsBucket.arnForObjects('reportblocks/*'),
        props.scoreResultAttachmentsBucket.arnForObjects('scoreresults/*'),
        props.scoreResultAttachmentsBucket.arnForObjects('evaluations/*'),
      ],
    }));
    taskRole.addToPolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
      resources: [...props.bedrockModelResources],
    }));
    repository.grantPull(executionRole);
    runtimeConfigSecret.grantRead(executionRole);
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'CommandWorkerTaskDefinition', {
      cpu: 1024,
      memoryLimitMiB: 4096,
      taskRole,
      executionRole,
      runtimePlatform: { cpuArchitecture: ecs.CpuArchitecture.X86_64, operatingSystemFamily: ecs.OperatingSystemFamily.LINUX },
    });
    taskRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ecs:GetTaskProtection', 'ecs:UpdateTaskProtection'],
      resources: [`${stack.formatArn({ service: 'ecs', resource: 'task', resourceName: `${cluster.clusterName}/*` })}`],
      conditions: { ArnEquals: { 'ecs:cluster': cluster.clusterArn } },
    }));
    taskDefinition.addContainer('CommandWorkerContainer', {
      image: ecs.ContainerImage.fromEcrRepository(repository, imageDigest),
      command: [],
      environment: {
        COMMAND_QUEUE_URL: this.commandQueue.queueUrl,
        PLEXUS_API_URL: props.apiUrl,
        PLEXUS_GRAPHQL_AUTH_MODE: 'iam',
        AMPLIFY_STORAGE_DATASETS_BUCKET_NAME: props.dataSourcesBucket.bucketName,
        AMPLIFY_STORAGE_DATASOURCES_BUCKET_NAME: props.dataSourcesBucket.bucketName,
        AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME: props.reportBlockDetailsBucket.bucketName,
        AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME: props.scoreResultAttachmentsBucket.bucketName,
        COMMAND_WORKER_EXECUTOR_FACTORY: 'plexus.command_worker.executors.plexus_cli:create_executor',
        COMMAND_WORKER_LEASE_SECONDS: '3600',
        COMMAND_WORKER_HEARTBEAT_SECONDS: '300',
        COMMAND_WORKER_VISIBILITY_TIMEOUT_SECONDS: '43200',
      },
      secrets: {
        OPENAI_API_KEY: ecs.Secret.fromSecretsManager(runtimeConfigSecret, 'openai-api-key'),
      },
      logging: ecs.LogDrivers.awsLogs({ logGroup: workerLogGroup, streamPrefix: 'command-worker' }),
    });
    this.workerService = new ecs.FargateService(this, 'CommandWorkerService', {
      cluster,
      taskDefinition,
      desiredCount: 1,
      assignPublicIp: false,
      securityGroups: [securityGroup],
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      circuitBreaker: { rollback: true },
      minHealthyPercent: 100,
      maxHealthyPercent: 200,
    });
    const serviceAlarm = new cloudwatch.Alarm(this, 'CommandWorkerRunningTaskAlarm', {
      metric: new cloudwatch.Metric({
        namespace: 'ECS/ContainerInsights',
        metricName: 'RunningTaskCount',
        dimensionsMap: { ClusterName: cluster.clusterName, ServiceName: this.workerService.serviceName },
        period: Duration.minutes(1),
        statistic: 'Minimum',
      }),
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.BREACHING,
    });
    serviceAlarm.node.addDependency(this.workerService);

    new CfnOutput(this, 'CommandQueueUrl', { value: this.commandQueue.queueUrl });
    new CfnOutput(this, 'CommandWorkerServiceName', { value: this.workerService.serviceName });
  }
}
