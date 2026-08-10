import { CfnOutput, Duration, Stack } from 'aws-cdk-lib';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { Construct } from 'constructs';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { IBucket } from 'aws-cdk-lib/aws-s3';
import { TaskStreamDispatcher } from '../functions/taskDispatcher/resource';
import { LIFECYCLE_APPSYNC_ROOTS, WORKER_DOMAIN_APPSYNC_ROOTS, appSyncFieldArn } from './authority-manifest';

export interface CommandWorkerFargateServiceProps {
  readonly taskTable: ITable;
  readonly taskTableStreamArn: string;
  readonly vpc: ec2.IVpc;
  /** Caller resolves the image: an immutable ECR digest for a long-lived
   * environment, or a CDK Docker asset for a sandbox that wants current
   * local code. */
  readonly image: ecs.ContainerImage;
  readonly apiUrl: string;
  readonly apiGraphqlArn: string;
  readonly configSecretName: string;
  readonly bedrockModelResources: readonly string[];
  readonly dataSourcesBucket: IBucket;
  readonly reportBlockDetailsBucket: IBucket;
  readonly scoreResultAttachmentsBucket: IBucket;
  readonly logRetention?: logs.RetentionDays;
  readonly leaseDuration?: Duration;
  readonly heartbeatInterval?: Duration;
  readonly visibilityTimeout?: Duration;
}

/**
 * The queue, dispatcher, and Fargate worker for the Task-authoritative
 * command service. Shared by the long-lived `CommandServiceStack` and a
 * sandbox stack that borrows a long-lived VPC and builds its own worker
 * image asset.
 */
export class CommandWorkerFargateService extends Construct {
  public readonly commandQueue: sqs.Queue;
  public readonly commandDeadLetterQueue: sqs.Queue;
  public readonly dispatcherFailureQueue: sqs.Queue;
  public readonly dispatcherFunction: lambda.Function;
  public readonly workerService: ecs.FargateService;

  constructor(scope: Construct, id: string, props: CommandWorkerFargateServiceProps) {
    super(scope, id);

    const leaseDuration = props.leaseDuration ?? Duration.hours(1);
    const heartbeatInterval = props.heartbeatInterval ?? Duration.minutes(5);
    const visibilityTimeout = props.visibilityTimeout ?? Duration.hours(12);

    const dispatcher = new TaskStreamDispatcher(this, 'TaskStreamDispatcher', {
      taskTable: props.taskTable,
      taskTableStreamArn: props.taskTableStreamArn,
      commandQueueVisibilityTimeout: visibilityTimeout,
    });
    this.commandQueue = dispatcher.commandQueue;
    this.commandDeadLetterQueue = dispatcher.commandDeadLetterQueue;
    this.dispatcherFailureQueue = dispatcher.dispatcherFailureQueue;
    this.dispatcherFunction = dispatcher.dispatcherFunction;

    const workerLogGroup = new logs.LogGroup(this, 'CommandWorkerLogGroup', {
      retention: props.logRetention ?? logs.RetentionDays.ONE_MONTH,
    });
    const cluster = new ecs.Cluster(this, 'CommandWorkerCluster', {
      vpc: props.vpc,
      containerInsightsV2: ecs.ContainerInsights.ENABLED,
    });
    const securityGroup = new ec2.SecurityGroup(this, 'CommandWorkerSecurityGroup', {
      vpc: props.vpc,
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
    taskRole.addToPolicy(new iam.PolicyStatement({
      actions: ['appsync:GraphQL'],
      resources: [...LIFECYCLE_APPSYNC_ROOTS, ...WORKER_DOMAIN_APPSYNC_ROOTS]
        .map((root) => appSyncFieldArn(props.apiGraphqlArn, root)),
    }));
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
    runtimeConfigSecret.grantRead(executionRole);
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'CommandWorkerTaskDefinition', {
      cpu: 1024,
      memoryLimitMiB: 4096,
      ephemeralStorageGiB: 50,
      taskRole,
      executionRole,
      runtimePlatform: { cpuArchitecture: ecs.CpuArchitecture.X86_64, operatingSystemFamily: ecs.OperatingSystemFamily.LINUX },
    });
    taskRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ecs:GetTaskProtection', 'ecs:UpdateTaskProtection'],
      resources: [Stack.of(this).formatArn({ service: 'ecs', resource: 'task', resourceName: `${cluster.clusterName}/*` })],
      conditions: { ArnEquals: { 'ecs:cluster': cluster.clusterArn } },
    }));
    taskDefinition.addContainer('CommandWorkerContainer', {
      image: props.image,
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
        COMMAND_WORKER_LEASE_SECONDS: `${leaseDuration.toSeconds()}`,
        COMMAND_WORKER_HEARTBEAT_SECONDS: `${heartbeatInterval.toSeconds()}`,
        COMMAND_WORKER_VISIBILITY_TIMEOUT_SECONDS: `${visibilityTimeout.toSeconds()}`,
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
