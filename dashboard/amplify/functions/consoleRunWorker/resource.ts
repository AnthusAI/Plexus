import { Duration, Stack, StackProps } from "aws-cdk-lib";
import { Effect, PolicyStatement } from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as sqs from "aws-cdk-lib/aws-sqs";
import { Construct } from "constructs";
import * as path from "path";
import { existsSync } from "fs";

interface ConsoleRunWorkerStackProps extends StackProps {
  plexusApiUrl?: string;
  plexusApiKey?: string;
}

export class ConsoleRunWorkerStack extends Stack {
  public readonly queue: sqs.Queue;
  public readonly deadLetterQueue: sqs.Queue;
  public readonly workerFunction: lambda.DockerImageFunction;

  constructor(scope: Construct, id: string, props: ConsoleRunWorkerStackProps = {}) {
    super(scope, id, props);

    this.deadLetterQueue = new sqs.Queue(this, "ConsoleRunWorkerDlq", {
      retentionPeriod: Duration.days(14),
    });

    this.queue = new sqs.Queue(this, "ConsoleRunWorkerQueue", {
      visibilityTimeout: Duration.minutes(15),
      retentionPeriod: Duration.days(4),
      deadLetterQueue: {
        maxReceiveCount: 3,
        queue: this.deadLetterQueue,
      },
    });

    const cwd = process.cwd();
    const repoRootCandidates = [
      cwd,
      path.resolve(cwd, ".."),
      path.resolve(cwd, "../.."),
      path.resolve(cwd, "../../.."),
    ];
    const repoRoot = repoRootCandidates.find((candidate) => (
      existsSync(path.join(candidate, "dashboard", "amplify", "functions", "consoleRunWorker", "Dockerfile"))
    )) || path.resolve(cwd, "..");
    this.workerFunction = new lambda.DockerImageFunction(this, "ConsoleRunWorkerFunction", {
      code: lambda.DockerImageCode.fromImageAsset(repoRoot, {
        file: "dashboard/amplify/functions/consoleRunWorker/Dockerfile",
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
  }
}
