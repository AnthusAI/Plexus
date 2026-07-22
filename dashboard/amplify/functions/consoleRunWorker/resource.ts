import { CfnOutput, Duration, NestedStack, NestedStackProps } from "aws-cdk-lib";
import { Effect, PolicyStatement } from "aws-cdk-lib/aws-iam";
import * as ecr_assets from "aws-cdk-lib/aws-ecr-assets";
import * as lambda from "aws-cdk-lib/aws-lambda";
import { ITable } from "aws-cdk-lib/aws-dynamodb";
import { IBucket } from "aws-cdk-lib/aws-s3";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import * as ssm from "aws-cdk-lib/aws-ssm";
import { fileURLToPath } from "node:url";
import { Construct } from "constructs";

interface ConsoleChatResponderStackProps extends NestedStackProps {
  chatMessageTable: ITable;
  plexusApiUrl?: string;
  environmentName?: string;
  asyncTasksAvailable?: boolean;
  responderParameterName: string;
  configSecretName?: string;
  reportBlockDetailsBucket?: IBucket;
}

export class ConsoleChatResponderStack extends NestedStack {
  public readonly responderFunction: lambda.DockerImageFunction;
  public readonly responderAlias: lambda.Alias;

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
    const workerImage = new ecr_assets.DockerImageAsset(this, "ConsoleChatResponderImage", {
      directory: repoRootPath,
      file: workerDockerfilePath,
      platform: ecr_assets.Platform.LINUX_AMD64,
    });
    const lambdaEnvironment: Record<string, string> = {
      PLEXUS_API_URL: props.plexusApiUrl || process.env.PLEXUS_API_URL || "",
      PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT: "false",
      PLEXUS_GRAPHQL_AUTH_MODE: "iam",
      PLEXUS_CONFIG_SECRET_NAME: configSecretName,
      PYTHONUNBUFFERED: "1",
      CONSOLE_RESPONSE_TARGET: "cloud",
      DSPY_DISABLE_DISK_CACHE: "true",
      DSPY_CACHEDIR: "/tmp/.dspy_cache",
      PLEXUS_DISABLE_BACKGROUND_LOGGING: "true",
      PLEXUS_CONSOLE_ASYNC_TASKS_AVAILABLE: props.asyncTasksAvailable === false ? "false" : "true",
      // Provisioned concurrency initializes the alias before it receives
      // traffic. Move the Console's expensive reusable imports and tool
      // registration into that initialization window instead of charging the
      // first chat request for them.
      PLEXUS_EAGER_CONSOLE_RUNTIME: "true",
      // DockerImageCode.fromImageAsset rewrites the image URI only after CDK
      // hashes the enclosing nested template. Keep the image content hash in
      // the template itself so a worker-only change produces a new nested
      // stack input instead of silently reusing the previous Lambda version.
      CONSOLE_WORKER_IMAGE_ASSET_HASH: workerImage.assetHash,
    };

    if (props.reportBlockDetailsBucket) {
      lambdaEnvironment.AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME = props.reportBlockDetailsBucket.bucketName;
    }

    this.responderFunction = new lambda.DockerImageFunction(this, "ConsoleChatResponderFunction", {
      code: lambda.DockerImageCode.fromEcr(workerImage.repository, {
        tagOrDigest: workerImage.imageTag,
      }),
      timeout: Duration.minutes(15),
      memorySize: 2048,
      environment: lambdaEnvironment,
    });
    this.responderAlias = new lambda.Alias(this, "InteractiveResponderAlias", {
      aliasName: "interactive",
      version: this.responderFunction.currentVersion,
      provisionedConcurrentExecutions: 1,
    });
    // Keep the dispatcher decoupled from this nested stack. A direct CDK
    // reference would form a cycle through the data stack that owns the
    // mutation handler.  The parameter is account-local and contains only
    // the alias ARN; each dispatch Lambda caches it after its first lookup.
    new ssm.StringParameter(this, "InteractiveResponderParameter", {
      parameterName: props.responderParameterName,
      stringValue: this.responderAlias.functionArn,
    });

    configSecret.grantRead(this.responderFunction);

    if (props.reportBlockDetailsBucket) {
      props.reportBlockDetailsBucket.grantReadWrite(this.responderFunction);
    }

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

    // The Console runtime records latency and worker-health metrics directly.
    // CloudWatch metric publication does not support resource-level ARNs, so
    // scope this statement to the one required action.
    this.responderFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ["cloudwatch:PutMetricData"],
        resources: ["*"],
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
      value: this.responderAlias.functionArn,
    });
  }
}
