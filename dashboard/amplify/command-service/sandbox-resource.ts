import { Duration, Stack, StackProps } from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as ecr_assets from 'aws-cdk-lib/aws-ecr-assets';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import { Construct } from 'constructs';
import { ITable } from 'aws-cdk-lib/aws-dynamodb';
import { IBucket } from 'aws-cdk-lib/aws-s3';
import { fileURLToPath } from 'node:url';
import { CommandWorkerFargateService } from './worker-service';

const STAGING_CONTRACT_PREFIX = '/plexus/staging/command-service';
const PRODUCTION_CONFIG_SECRET_NAME = 'plexus/production/config';

export interface SandboxCommandWorkerStackProps extends StackProps {
  readonly taskTable: ITable;
  readonly taskTableStreamArn: string;
  readonly apiUrl: string;
  readonly apiGraphqlArn: string;
  readonly bedrockModelResources: readonly string[];
  /** Defaults to plexus/staging/config; must never be plexus/production/config. */
  readonly configSecretName?: string;
  readonly dataSourcesBucket: IBucket;
  readonly reportBlockDetailsBucket: IBucket;
  readonly scoreResultAttachmentsBucket: IBucket;
}

/**
 * A personal-sandbox command worker for fast end-to-end iteration without a
 * staging deploy. Borrows the staging foundation's VPC (same AWS account,
 * no sandbox-specific network) and builds the worker image inline as a CDK
 * Docker asset from the current checkout, so the sandbox runs local code
 * rather than a pinned staging digest. Staging remains the final ECS/IAM/
 * network acceptance environment; this stack has no activity-gate policy
 * and no foundation dependency, since an ephemeral sandbox has no deployed
 * task to protect.
 */
export class SandboxCommandWorkerStack extends Stack {
  public readonly commandQueue: sqs.Queue;
  public readonly commandDeadLetterQueue: sqs.Queue;
  public readonly dispatcherFailureQueue: sqs.Queue;
  public readonly dispatcherFunction: lambda.Function;
  public readonly workerService: ecs.FargateService;

  constructor(scope: Construct, id: string, props: SandboxCommandWorkerStackProps) {
    super(scope, id, props);
    const configSecretName = (props.configSecretName || 'plexus/staging/config').trim();
    if (configSecretName === PRODUCTION_CONFIG_SECRET_NAME) {
      throw new Error('Sandbox command worker must not use plexus/production/config');
    }

    const vpc = ec2.Vpc.fromVpcAttributes(this, 'StagingFoundationVpc', {
      vpcId: ssm.StringParameter.valueForStringParameter(this, `${STAGING_CONTRACT_PREFIX}/vpc-id`),
      availabilityZones: ssm.StringParameter.valueForStringParameter(this, `${STAGING_CONTRACT_PREFIX}/availability-zones`).split(','),
      privateSubnetIds: ssm.StringParameter.valueForStringParameter(this, `${STAGING_CONTRACT_PREFIX}/private-subnet-ids`).split(','),
    });

    const repoRootPath = fileURLToPath(new URL('../../../', import.meta.url));
    const workerImageAsset = new ecr_assets.DockerImageAsset(this, 'CommandWorkerImage', {
      directory: repoRootPath,
      file: 'plexus/command_worker/Dockerfile',
      platform: ecr_assets.Platform.LINUX_AMD64,
    });

    const service = new CommandWorkerFargateService(this, 'CommandWorkerFargateService', {
      taskTable: props.taskTable,
      taskTableStreamArn: props.taskTableStreamArn,
      vpc,
      image: ecs.ContainerImage.fromDockerImageAsset(workerImageAsset),
      apiUrl: props.apiUrl,
      apiGraphqlArn: props.apiGraphqlArn,
      configSecretName,
      bedrockModelResources: props.bedrockModelResources,
      dataSourcesBucket: props.dataSourcesBucket,
      reportBlockDetailsBucket: props.reportBlockDetailsBucket,
      scoreResultAttachmentsBucket: props.scoreResultAttachmentsBucket,
      leaseDuration: Duration.minutes(5),
      heartbeatInterval: Duration.minutes(1),
      visibilityTimeout: Duration.minutes(10),
    });
    this.commandQueue = service.commandQueue;
    this.commandDeadLetterQueue = service.commandDeadLetterQueue;
    this.dispatcherFailureQueue = service.dispatcherFailureQueue;
    this.dispatcherFunction = service.dispatcherFunction;
    this.workerService = service.workerService;
  }
}
