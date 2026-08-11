import { Fn, Stack } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { Construct } from 'constructs';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { IBucket } from 'aws-cdk-lib/aws-s3';
import { CommandWorkerFargateService } from './worker-service';

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

    const service = new CommandWorkerFargateService(this, 'CommandWorkerFargateService', {
      taskTable: props.taskTable,
      taskTableStreamArn: props.taskTableStreamArn,
      vpc,
      image: ecs.ContainerImage.fromEcrRepository(repository, imageDigest),
      apiUrl: props.apiUrl,
      apiGraphqlArn: props.apiGraphqlArn,
      configSecretName: props.configSecretName,
      bedrockModelResources: props.bedrockModelResources,
      dataSourcesBucket: props.dataSourcesBucket,
      reportBlockDetailsBucket: props.reportBlockDetailsBucket,
      scoreResultAttachmentsBucket: props.scoreResultAttachmentsBucket,
      logRetention: environment === 'production' ? logs.RetentionDays.THREE_MONTHS : logs.RetentionDays.ONE_MONTH,
    });
    this.commandQueue = service.commandQueue;
    this.commandDeadLetterQueue = service.commandDeadLetterQueue;
    this.dispatcherFailureQueue = service.dispatcherFailureQueue;
    this.dispatcherFunction = service.dispatcherFunction;
    this.workerService = service.workerService;
  }
}
