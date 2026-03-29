import { CfnOutput, Duration, Stack, StackProps } from "aws-cdk-lib";
import { Effect, PolicyStatement } from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import { SqsEventSource } from "aws-cdk-lib/aws-lambda-event-sources";
import * as sqs from "aws-cdk-lib/aws-sqs";
import { Construct } from "constructs";
import * as path from "path";
import { cpSync, mkdirSync, mkdtempSync, readdirSync, rmSync } from "fs";
import { tmpdir } from "os";
import { execFileSync } from "child_process";

interface ConsoleRunWorkerStackProps extends StackProps {
  plexusApiUrl?: string;
  plexusApiKey?: string;
  reservedConcurrency?: number;
  provisionedConcurrency?: number;
  streamUpdateMaxIntervalSeconds?: string;
  streamUpdateMinCharsDelta?: string;
}

export class ConsoleRunWorkerStack extends Stack {
  public readonly queue: sqs.Queue;
  public readonly deadLetterQueue: sqs.Queue;
  public readonly workerFunction: lambda.Function;

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

    const functionDir = path.join(process.cwd(), "amplify/functions/consoleRunWorker");
    const repoRoot = path.resolve(process.cwd(), "..");

    this.workerFunction = new lambda.Function(this, "ConsoleRunWorkerFunction", {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "app.handler",
      code: lambda.Code.fromAsset(functionDir, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          local: {
            tryBundle(outputDir: string) {
              const packageDir = mkdtempSync(path.join(tmpdir(), "console-worker-"));
              mkdirSync(outputDir, { recursive: true });

              try {
                execFileSync(
                  "python3",
                  [
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    path.join(functionDir, "requirements.txt"),
                    "-t",
                    packageDir,
                    "--platform",
                    "manylinux2014_x86_64",
                    "--implementation",
                    "cp",
                    "--python",
                    "3.11",
                    "--only-binary=:all:",
                    "--upgrade",
                  ],
                  { stdio: "inherit" },
                );

                for (const entry of readdirSync(packageDir)) {
                  cpSync(path.join(packageDir, entry), path.join(outputDir, entry), {
                    recursive: true,
                    force: true,
                  });
                }

                cpSync(path.join(functionDir, "app.py"), path.join(outputDir, "app.py"), {
                  force: true,
                });

                cpSync(path.join(repoRoot, "plexus"), path.join(outputDir, "plexus"), {
                  recursive: true,
                  force: true,
                });
              } finally {
                rmSync(packageDir, { recursive: true, force: true });
              }

              return true;
            },
          },
        },
      }),
      timeout: Duration.minutes(15),
      memorySize: 2048,
      reservedConcurrentExecutions: props.reservedConcurrency,
      environment: {
        PLEXUS_API_URL: props.plexusApiUrl || process.env.PLEXUS_API_URL || "",
        PLEXUS_API_KEY: props.plexusApiKey || process.env.PLEXUS_API_KEY || "",
        PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT: "false",
        PLEXUS_STREAM_UPDATE_MAX_INTERVAL_SECONDS: props.streamUpdateMaxIntervalSeconds || "0.35",
        PLEXUS_STREAM_UPDATE_MIN_CHARS_DELTA: props.streamUpdateMinCharsDelta || "20",
        OPENAI_API_KEY: process.env.OPENAI_API_KEY || "",
        OPENAI_BASE_URL: process.env.OPENAI_BASE_URL || "",
        OPENAI_API_BASE: process.env.OPENAI_API_BASE || "",
        PYTHONPATH: "/var/task",
        PYTHONUNBUFFERED: "1",
      },
    });

    let eventSourceTarget: lambda.IFunction = this.workerFunction;
    if (props.provisionedConcurrency && props.provisionedConcurrency > 0) {
      const liveAlias = new lambda.Alias(this, "ConsoleRunWorkerLiveAlias", {
        aliasName: "live",
        version: this.workerFunction.currentVersion,
        provisionedConcurrentExecutions: props.provisionedConcurrency,
      });
      eventSourceTarget = liveAlias;
    }

    eventSourceTarget.addEventSource(
      new SqsEventSource(this.queue, {
        batchSize: 1,
        reportBatchItemFailures: true,
      }),
    );

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
