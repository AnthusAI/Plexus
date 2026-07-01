import { CfnOutput, Duration, NestedStack, NestedStackProps } from "aws-cdk-lib";
import { Effect, PolicyStatement } from "aws-cdk-lib/aws-iam";
import * as ecr_assets from "aws-cdk-lib/aws-ecr-assets";
import * as lambda from "aws-cdk-lib/aws-lambda";
import { StartingPosition } from "aws-cdk-lib/aws-lambda";
import { DynamoEventSource } from "aws-cdk-lib/aws-lambda-event-sources";
import { ITable } from "aws-cdk-lib/aws-dynamodb";
import { IBucket } from "aws-cdk-lib/aws-s3";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { fileURLToPath } from "node:url";
import { Construct } from "constructs";

interface ConsoleChatResponderStackProps extends NestedStackProps {
  chatMessageTable: ITable;
  plexusApiUrl?: string;
  environmentName?: string;
  configSecretName?: string;
  reportBlockDetailsBucket?: IBucket;
}

export class ConsoleChatResponderStack extends NestedStack {
  public readonly responderFunction: lambda.DockerImageFunction;

  constructor(scope: Construct, id: string, props: ConsoleChatResponderStackProps) {
    super(scope, id, props);
    const repoRootPath = fileURLToPath(new URL("../../../../", import.meta.url));
    const workerDockerfilePath = "dashboard/amplify/functions/consoleRunWorker/Dockerfile";
    const environmentName = props.environmentName || "staging";
    const configSecretName = (
      props.configSecretName ||
      process.env.PLEXUS_CONFIG_SECRET_NAME ||
      `plexus/${environmentName}/config`
    ).trim();

    if (!configSecretName) {
      throw new Error("PLEXUS_CONFIG_SECRET_NAME must be set for ConsoleRunWorkerStack deployment");
    }
    const configSecret = secretsmanager.Secret.fromSecretNameV2(
      this,
      "PlexusConfigSecret",
      configSecretName,
    );
    const lambdaEnvironment: Record<string, string> = {
      PLEXUS_API_URL: props.plexusApiUrl || process.env.PLEXUS_API_URL || "",
      PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT: "false",
      PLEXUS_GRAPHQL_AUTH_MODE: "iam",
      PLEXUS_CONFIG_SECRET_NAME: configSecretName,
      PYTHONUNBUFFERED: "1",
      CONSOLE_RESPONSE_TARGET: "cloud",
      DSPY_DISABLE_DISK_CACHE: "true",
      DSPY_CACHEDIR: "/tmp/.dspy_cache",
    };

    if (props.reportBlockDetailsBucket) {
      lambdaEnvironment.AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME = props.reportBlockDetailsBucket.bucketName;
    }

    this.responderFunction = new lambda.DockerImageFunction(this, "ConsoleChatResponderFunction", {
      code: lambda.DockerImageCode.fromImageAsset(repoRootPath, {
        file: workerDockerfilePath,
        platform: ecr_assets.Platform.LINUX_AMD64,
      }),
      timeout: Duration.minutes(15),
      memorySize: 2048,
      environment: lambdaEnvironment,
    });

    configSecret.grantRead(this.responderFunction);

    if (props.reportBlockDetailsBucket) {
      props.reportBlockDetailsBucket.grantReadWrite(this.responderFunction);
    }

    this.responderFunction.addEventSource(new DynamoEventSource(props.chatMessageTable, {
      startingPosition: StartingPosition.LATEST,
      batchSize: 1,
      reportBatchItemFailures: true,
      retryAttempts: 2,
    }));

    this.responderFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["appsync:GraphQL"],
        resources: ["*"],
      }),
    );

    this.responderFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
          "logs:PutDataProtectionPolicy",
        ],
        resources: [
          "arn:aws:logs:*:*:log-group:/plexus/procedures/*",
          "arn:aws:logs:*:*:log-group:/plexus/procedures/*:*",
          "arn:aws:logs:*:*:log-group:/plexus/console/*",
          "arn:aws:logs:*:*:log-group:/plexus/console/*:*",
        ],
      }),
    );

    // SSM Parameter Store permissions for console chat JWT and other secrets
    this.responderFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          "ssm:GetParameter",
          "ssm:GetParameters",
        ],
        resources: [
          `arn:aws:ssm:*:*:parameter/plexus/*`,
          `arn:aws:ssm:*:*:parameter/amplify/*`,
        ],
      }),
    );

    new CfnOutput(this, "ConsoleChatResponderFunctionArn", {
      value: this.responderFunction.functionArn,
    });
  }
}
