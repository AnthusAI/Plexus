import { CfnOutput, Duration, NestedStack, NestedStackProps } from "aws-cdk-lib";
import * as ecr from "aws-cdk-lib/aws-ecr";
import { Effect, PolicyStatement } from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import { StartingPosition } from "aws-cdk-lib/aws-lambda";
import { DynamoEventSource } from "aws-cdk-lib/aws-lambda-event-sources";
import { ITable } from "aws-cdk-lib/aws-dynamodb";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

interface ConsoleChatResponderStackProps extends NestedStackProps {
  chatMessageTable: ITable;
  plexusApiUrl?: string;
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

export class ConsoleChatResponderStack extends NestedStack {
  public readonly responderFunction: lambda.DockerImageFunction;

  constructor(scope: Construct, id: string, props: ConsoleChatResponderStackProps) {
    super(scope, id, props);
    const workerImage = parseEcrImageUri(
      props.workerImageUri || process.env.CONSOLE_WORKER_IMAGE_URI || "",
    );
    const environmentName = props.environmentName || "staging";
    const configSecretName = `plexus/${environmentName}/config`;
    const configSecret = secretsmanager.Secret.fromSecretNameV2(
      this,
      "PlexusConfigSecret",
      configSecretName,
    );
    const workerImageRepository = ecr.Repository.fromRepositoryName(
      this,
      "ConsoleRunWorkerImageRepository",
      workerImage.repositoryName,
    );
    this.responderFunction = new lambda.DockerImageFunction(this, "ConsoleChatResponderFunction", {
      code: lambda.DockerImageCode.fromEcr(workerImageRepository, {
        tagOrDigest: workerImage.tagOrDigest,
      }),
      timeout: Duration.minutes(15),
      memorySize: 2048,
      environment: {
        PLEXUS_API_URL: props.plexusApiUrl || process.env.PLEXUS_API_URL || "",
        PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT: "false",
        PLEXUS_GRAPHQL_AUTH_MODE: "iam",
        PLEXUS_CONFIG_SECRET_NAME: configSecretName,
        PYTHONUNBUFFERED: "1",
        CONSOLE_RESPONSE_TARGET: "cloud",
      },
    });

    configSecret.grantRead(this.responderFunction);

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
        ],
        resources: [
          "arn:aws:logs:*:*:log-group:/plexus/procedures/*",
          "arn:aws:logs:*:*:log-group:/plexus/procedures/*:*",
        ],
      }),
    );

    new CfnOutput(this, "ConsoleChatResponderFunctionArn", {
      value: this.responderFunction.functionArn,
    });
  }
}
