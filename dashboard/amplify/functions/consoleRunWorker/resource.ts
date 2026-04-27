import { CfnOutput, Duration, NestedStack, NestedStackProps } from "aws-cdk-lib";
import * as ecr from "aws-cdk-lib/aws-ecr";
import { Effect, PolicyStatement } from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as sqs from "aws-cdk-lib/aws-sqs";
import { Construct } from "constructs";

interface ConsoleRunWorkerStackProps extends NestedStackProps {
  plexusApiUrl?: string;
  plexusApiKey?: string;
  workerImageUri?: string;
  environmentName?: string;
}

interface ParsedEcrImageUri {
  repositoryName: string;
  tagOrDigest: string;
}

const parseEcrImageUri = (imageUri: string): ParsedEcrImageUri => {
  const trimmed = imageUri.trim();
  if (!trimmed) {
    throw new Error("CONSOLE_WORKER_IMAGE_URI must be set to a full ECR image URI");
  }

  const firstSlashIndex = trimmed.indexOf("/");
  if (firstSlashIndex <= 0 || firstSlashIndex === trimmed.length - 1) {
    throw new Error(
      `CONSOLE_WORKER_IMAGE_URI must include a repository and tag/digest. Received: "${trimmed}"`,
    );
  }

  const repositoryAndReference = trimmed.slice(firstSlashIndex + 1);
  const digestSeparatorIndex = repositoryAndReference.lastIndexOf("@");
  if (digestSeparatorIndex > 0 && digestSeparatorIndex < repositoryAndReference.length - 1) {
    const repositoryName = repositoryAndReference.slice(0, digestSeparatorIndex);
    const digest = repositoryAndReference.slice(digestSeparatorIndex + 1);
    if (!digest.startsWith("sha256:")) {
      throw new Error(
        `CONSOLE_WORKER_IMAGE_URI digest must start with "sha256:". Received: "${digest}"`,
      );
    }
    return { repositoryName, tagOrDigest: digest };
  }

  const tagSeparatorIndex = repositoryAndReference.lastIndexOf(":");
  if (tagSeparatorIndex <= 0 || tagSeparatorIndex === repositoryAndReference.length - 1) {
    throw new Error(
      `CONSOLE_WORKER_IMAGE_URI must include either @sha256:digest or :tag. Received: "${trimmed}"`,
    );
  }

  const repositoryName = repositoryAndReference.slice(0, tagSeparatorIndex);
  const tag = repositoryAndReference.slice(tagSeparatorIndex + 1);
  return { repositoryName, tagOrDigest: tag };
}

export class ConsoleRunWorkerStack extends NestedStack {
  public readonly queue: sqs.Queue;
  public readonly deadLetterQueue: sqs.Queue;
  public readonly workerFunction: lambda.DockerImageFunction;

  constructor(scope: Construct, id: string, props: ConsoleRunWorkerStackProps = {}) {
    super(scope, id, props);
    const environmentName = (props.environmentName || "staging").toLowerCase().replace(/[^a-z0-9-]/g, "-");

    this.deadLetterQueue = new sqs.Queue(this, "ConsoleRunWorkerDlq", {
      queueName: `plexus-console-run-worker-${environmentName}-dlq`,
      retentionPeriod: Duration.days(14),
    });

    this.queue = new sqs.Queue(this, "ConsoleRunWorkerQueue", {
      queueName: `plexus-console-run-worker-${environmentName}-queue`,
      visibilityTimeout: Duration.minutes(15),
      retentionPeriod: Duration.days(4),
      deadLetterQueue: {
        maxReceiveCount: 3,
        queue: this.deadLetterQueue,
      },
    });

    const workerImage = parseEcrImageUri(
      props.workerImageUri || process.env.CONSOLE_WORKER_IMAGE_URI || "",
    );
    const workerImageRepository = ecr.Repository.fromRepositoryName(
      this,
      "ConsoleRunWorkerImageRepository",
      workerImage.repositoryName,
    );
    this.workerFunction = new lambda.DockerImageFunction(this, "ConsoleRunWorkerFunction", {
      code: lambda.DockerImageCode.fromEcr(workerImageRepository, {
        tagOrDigest: workerImage.tagOrDigest,
      }),
      timeout: Duration.minutes(15),
      memorySize: 2048,
      environment: {
        PLEXUS_API_URL: props.plexusApiUrl || process.env.PLEXUS_API_URL || "",
        PLEXUS_API_KEY: props.plexusApiKey || process.env.PLEXUS_API_KEY || "",
        PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT: "false",
        PYTHONUNBUFFERED: "1",
      },
    });

    const workerVersion = this.workerFunction.currentVersion;
    new lambda.EventSourceMapping(this, "ConsoleRunWorkerQueueEventSource", {
      target: workerVersion,
      eventSourceArn: this.queue.queueArn,
      batchSize: 1,
      reportBatchItemFailures: true,
    });

    this.queue.grantConsumeMessages(this.workerFunction);
    this.deadLetterQueue.grantSendMessages(this.workerFunction);

    this.workerFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["appsync:GraphQL"],
        resources: ["*"],
      }),
    );

    new CfnOutput(this, "ConsoleRunWorkerQueueUrl", {
      value: this.queue.queueUrl,
    });
    new CfnOutput(this, "ConsoleRunWorkerFunctionArn", {
      value: this.workerFunction.functionArn,
    });
  }
}
