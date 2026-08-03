from __future__ import annotations

from collections.abc import Mapping, Sequence

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_authorizers as authorizers,
    aws_apigatewayv2_integrations as integrations,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_event_sources,
    aws_logs as logs,
    aws_s3 as s3,
    aws_secretsmanager as secretsmanager,
    aws_sns as sns,
    aws_sqs as sqs,
    aws_ssm as ssm,
)
from constructs import Construct


class ScoringServiceIntegrationStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        resource_prefix: str,
        display_name: str,
        environment: str,
        response_destination: str,
        response_worker_requires_sql_egress: bool,
        vpc: ec2.IVpc,
        serverless_runtime_image_tag: str,
        api_handler_command: Sequence[str],
        response_worker_handler_command: Sequence[str],
        health_route_path: str,
        prediction_route_path: str,
        scoring_scope_description: str,
        standard_request_queue: sqs.IQueue,
        response_queue: sqs.IQueue,
        runtime_config_secret_name: str | None = None,
        runtime_config_secret_complete_arn: str | None = None,
        api_memory_size_mb: int = 4096,
        response_worker_memory_size_mb: int = 2048,
        api_timeout: Duration = Duration.seconds(60),
        response_worker_timeout: Duration = Duration.minutes(5),
        sql_egress_cidrs: Sequence[str] = ("0.0.0.0/0",),
        sql_egress_ports: Sequence[int] = (1433,),
        read_bucket_parameters: Mapping[str, str],
        read_write_bucket_parameters: Mapping[str, str],
        bucket_environment_variables: Mapping[str, Sequence[str]],
        runtime_environment: Mapping[str, str],
        state_table_environment_variable: str,
        response_destination_environment_variable: str,
        runtime_secret_id_environment_variable: str,
        verification_scope_name: str | None,
        alert_topic: sns.ITopic,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if not resource_prefix.strip():
            raise ValueError("resource_prefix must not be empty")
        if not display_name.strip():
            raise ValueError("display_name must not be empty")
        if not response_destination.strip():
            raise ValueError("response_destination must not be empty")

        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Service", f"{resource_prefix}-serverless-app")
        Tags.of(self).add("Environment", environment)

        runtime_config_secret_name = (
            runtime_config_secret_name
            or f"{resource_prefix}/{environment}/runtime-config"
        )
        if runtime_config_secret_complete_arn:
            runtime_secret = secretsmanager.Secret.from_secret_complete_arn(
                self,
                "RuntimeConfigSecret",
                runtime_config_secret_complete_arn,
            )
        else:
            runtime_secret = secretsmanager.Secret.from_secret_name_v2(
                self,
                "RuntimeConfigSecret",
                runtime_config_secret_name,
            )
        read_buckets = self._resolve_bucket_parameters(read_bucket_parameters)
        read_write_buckets = self._resolve_bucket_parameters(
            read_write_bucket_parameters
        )

        repository = ecr.Repository.from_repository_name(
            self,
            "ServerlessRuntimeRepository",
            repository_name=f"{resource_prefix}-serverless-runtime-{environment}",
        )
        runtime_config_secret_id = (
            runtime_config_secret_complete_arn or runtime_config_secret_name
        )

        async_state_table = dynamodb.Table(
            self,
            "AsyncStateTable",
            table_name=f"{resource_prefix}-async-state-{environment}",
            partition_key=dynamodb.Attribute(
                name="pk",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            time_to_live_attribute="expires_at",
            point_in_time_recovery_specification=(
                dynamodb.PointInTimeRecoverySpecification(
                    point_in_time_recovery_enabled=environment == "production"
                )
            ),
            removal_policy=RemovalPolicy.RETAIN,
            deletion_protection=environment == "production",
        )

        score_scope = cognito.ResourceServerScope(
            scope_name="score",
            scope_description=scoring_scope_description,
        )
        resource_server_scopes = [score_scope]
        verification_scope = None
        if verification_scope_name:
            verification_scope = cognito.ResourceServerScope(
                scope_name=verification_scope_name,
                scope_description="Verify rejection of insufficiently scoped tokens",
            )
            resource_server_scopes.append(verification_scope)

        api_user_pool = cognito.UserPool(
            self,
            "ApiUserPool",
            user_pool_name=f"{resource_prefix}-api-{environment}",
            self_sign_up_enabled=False,
            deletion_protection=environment == "production",
            removal_policy=RemovalPolicy.RETAIN,
        )
        api_resource_server = api_user_pool.add_resource_server(
            "ApiResourceServer",
            identifier=resource_prefix,
            user_pool_resource_server_name=f"{display_name} API",
            scopes=resource_server_scopes,
        )
        api_client = api_user_pool.add_client(
            "ApiMachineClient",
            user_pool_client_name=f"{resource_prefix}-api-{environment}",
            generate_secret=True,
            access_token_validity=Duration.hours(1),
            enable_token_revocation=True,
            prevent_user_existence_errors=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[
                    cognito.OAuthScope.resource_server(
                        api_resource_server,
                        score_scope,
                    )
                ],
            ),
        )
        verification_client = None
        if verification_scope is not None:
            verification_client = api_user_pool.add_client(
                "ApiVerificationDeniedClient",
                user_pool_client_name=(
                    f"{resource_prefix}-api-{environment}-denied-scope"
                ),
                generate_secret=True,
                access_token_validity=Duration.hours(1),
                enable_token_revocation=True,
                prevent_user_existence_errors=True,
                o_auth=cognito.OAuthSettings(
                    flows=cognito.OAuthFlows(client_credentials=True),
                    scopes=[
                        cognito.OAuthScope.resource_server(
                            api_resource_server,
                            verification_scope,
                        )
                    ],
                ),
            )
        api_domain = api_user_pool.add_domain(
            "ApiUserPoolDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{resource_prefix}-{self.account}-{environment}"
            ),
        )

        api_security_group = ec2.SecurityGroup(
            self,
            "ServerlessRuntimeSecurityGroup",
            vpc=vpc,
            security_group_name=f"{resource_prefix}-serverless-runtime-{environment}",
            description=(
                f"Outbound-only security group for {display_name} {environment} "
                "Lambda runtime"
            ),
            allow_all_outbound=False,
        )
        response_worker_security_group = ec2.SecurityGroup(
            self,
            "ResponseWorkerSecurityGroup",
            vpc=vpc,
            security_group_name=f"{resource_prefix}-response-worker-{environment}",
            description=(
                f"Outbound-only security group for {display_name} {environment} "
                "response worker"
            ),
            allow_all_outbound=False,
        )
        for function_security_group in (
            api_security_group,
            response_worker_security_group,
        ):
            function_security_group.add_egress_rule(
                peer=ec2.Peer.any_ipv4(),
                connection=ec2.Port.tcp(443),
                description="Serverless runtime to public HTTPS APIs and AWS endpoints",
            )

        for cidr in sql_egress_cidrs:
            for port in sql_egress_ports:
                api_security_group.add_egress_rule(
                    peer=ec2.Peer.ipv4(cidr),
                    connection=ec2.Port.tcp(port),
                    description=f"API runtime to SQL endpoint tcp/{port}",
                )
                if response_worker_requires_sql_egress:
                    response_worker_security_group.add_egress_rule(
                        peer=ec2.Peer.ipv4(cidr),
                        connection=ec2.Port.tcp(port),
                        description=f"Response worker to SQL endpoint tcp/{port}",
                    )

        common_environment = {
            **runtime_environment,
            state_table_environment_variable: async_state_table.table_name,
            response_destination_environment_variable: response_destination,
            runtime_secret_id_environment_variable: runtime_config_secret_id,
            "FETCH_SCHEMA_FROM_TRANSPORT": "false",
            "GQL_FETCH_SCHEMA_FROM_TRANSPORT": "0",
            "MKL_NUM_THREADS": "1",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": "/tmp/mpl",
            "NUMEXPR_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "PLEXUS_DISABLE_CLOUDWATCH_LOGS": "1",
            "PLEXUS_FETCH_SCHEMA_FROM_TRANSPORT": "0",
            "PLEXUS_SCORING_WORKER_REQUEST_STANDARD_QUEUE_URL": (
                standard_request_queue.queue_url
            ),
            "PLEXUS_RESPONSE_WORKER_QUEUE_URL": response_queue.queue_url,
            "PYTHONUNBUFFERED": "1",
        }
        for bucket_id, environment_keys in bucket_environment_variables.items():
            buckets = read_buckets | read_write_buckets
            if bucket_id not in buckets:
                raise ValueError(
                    f"bucket environment binding references unknown bucket: {bucket_id}"
                )
            for environment_key in environment_keys:
                common_environment[environment_key] = buckets[bucket_id]

        function_log_retention = (
            logs.RetentionDays.THREE_MONTHS
            if environment == "production"
            else logs.RetentionDays.ONE_MONTH
        )
        api_log_group = logs.LogGroup(
            self,
            "ApiFunctionLogGroup",
            log_group_name=f"/aws/lambda/{resource_prefix}-api-{environment}",
            retention=function_log_retention,
            removal_policy=RemovalPolicy.RETAIN,
        )
        response_worker_log_group = logs.LogGroup(
            self,
            "ResponseWorkerFunctionLogGroup",
            log_group_name=(
                f"/aws/lambda/{resource_prefix}-response-worker-{environment}"
            ),
            retention=function_log_retention,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.api_function = lambda_.DockerImageFunction(
            self,
            "ApiFunction",
            function_name=f"{resource_prefix}-api-{environment}",
            code=lambda_.DockerImageCode.from_ecr(
                repository,
                tag_or_digest=serverless_runtime_image_tag,
                cmd=list(api_handler_command),
            ),
            architecture=lambda_.Architecture.X86_64,
            memory_size=api_memory_size_mb,
            timeout=api_timeout,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[api_security_group],
            log_group=api_log_group,
            environment=common_environment,
        )

        self.response_worker_function = lambda_.DockerImageFunction(
            self,
            "ResponseWorkerFunction",
            function_name=f"{resource_prefix}-response-worker-{environment}",
            code=lambda_.DockerImageCode.from_ecr(
                repository,
                tag_or_digest=serverless_runtime_image_tag,
                cmd=list(response_worker_handler_command),
            ),
            architecture=lambda_.Architecture.X86_64,
            memory_size=response_worker_memory_size_mb,
            timeout=response_worker_timeout,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[response_worker_security_group],
            log_group=response_worker_log_group,
            environment=common_environment,
        )

        self.response_worker_function.add_event_source(
            lambda_event_sources.SqsEventSource(
                response_queue,
                batch_size=5,
                report_batch_item_failures=True,
            )
        )

        self.api = apigwv2.HttpApi(
            self,
            "AsyncHttpApi",
            api_name=f"{resource_prefix}-api-{environment}",
            create_default_stage=False,
            disable_execute_api_endpoint=False,
        )
        api_integration = integrations.HttpLambdaIntegration(
            "ApiLambdaIntegration",
            self.api_function,
        )
        jwt_authorizer = authorizers.HttpJwtAuthorizer(
            "ApiJwtAuthorizer",
            api_user_pool.user_pool_provider_url,
            authorizer_name=f"{resource_prefix}-api-{environment}",
            jwt_audience=[
                api_client.user_pool_client_id,
                *(
                    [verification_client.user_pool_client_id]
                    if verification_client is not None
                    else []
                ),
            ],
            identity_source=["$request.header.Authorization"],
        )
        self.api.add_routes(
            path=health_route_path,
            methods=[apigwv2.HttpMethod.GET],
            integration=api_integration,
        )
        self.api.add_routes(
            path=prediction_route_path,
            methods=[apigwv2.HttpMethod.GET, apigwv2.HttpMethod.POST],
            integration=api_integration,
            authorizer=jwt_authorizer,
            authorization_scopes=[f"{resource_prefix}/score"],
        )

        api_access_log_group = logs.LogGroup(
            self,
            "ApiGatewayAccessLogGroup",
            log_group_name=f"/aws/apigateway/{resource_prefix}-{environment}",
            retention=(
                logs.RetentionDays.THREE_MONTHS
                if environment == "production"
                else logs.RetentionDays.ONE_MONTH
            ),
            removal_policy=RemovalPolicy.RETAIN,
        )
        access_log_format = (
            '{"requestId":"$context.requestId",'
            '"sourceIp":"$context.identity.sourceIp",'
            '"requestTimeEpoch":"$context.requestTimeEpoch",'
            '"routeKey":"$context.routeKey",'
            '"status":"$context.status",'
            '"responseLatency":"$context.responseLatency",'
            '"integrationLatency":"$context.integrationLatency",'
            '"integrationError":"$context.integrationErrorMessage",'
            '"authorizerError":"$context.authorizer.error"}'
        )
        self.api_stage = apigwv2.HttpStage(
            self,
            "ApiDefaultStage",
            http_api=self.api,
            stage_name="$default",
            auto_deploy=True,
            detailed_metrics_enabled=True,
        )
        cfn_api_stage = self.api_stage.node.default_child
        if not isinstance(cfn_api_stage, apigwv2.CfnStage):
            raise RuntimeError("HTTP API stage has no CloudFormation resource")
        cfn_api_stage.access_log_settings = apigwv2.CfnStage.AccessLogSettingsProperty(
            destination_arn=api_access_log_group.log_group_arn,
            format=access_log_format,
        )

        api_metric_dimensions = {
            "ApiId": self.api.api_id,
            "Stage": self.api_stage.stage_name,
        }
        api_5xx_alarm = cloudwatch.Alarm(
            self,
            "Api5xxAlarm",
            alarm_name=f"{resource_prefix}-api-{environment}-5xx",
            metric=cloudwatch.Metric(
                namespace="AWS/ApiGateway",
                metric_name="5xx",
                dimensions_map=api_metric_dimensions,
                statistic="Sum",
                period=Duration.minutes(5),
            ),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=(
                cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
            ),
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        api_5xx_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alert_topic))

        repository.grant_pull(self.api_function)
        repository.grant_pull(self.response_worker_function)
        runtime_secret.grant_read(self.api_function)
        runtime_secret.grant_read(self.response_worker_function)
        standard_request_queue.grant_send_messages(self.api_function)
        response_queue.grant_consume_messages(self.response_worker_function)
        self.api_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:GetItem", "dynamodb:UpdateItem"],
                resources=[async_state_table.table_arn],
            )
        )
        self.response_worker_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:PutItem", "dynamodb:UpdateItem"],
                resources=[async_state_table.table_arn],
            )
        )

        self._grant_s3_access(
            functions=[self.api_function],
            read_buckets=read_buckets,
            read_write_buckets=read_write_buckets,
        )
        self.async_state_table = async_state_table

        CfnOutput(
            self,
            "ApiEndpoint",
            value=self.api.api_endpoint,
            export_name=f"{resource_prefix}-api-{environment}-endpoint",
        )
        CfnOutput(
            self,
            "ApiOAuthUserPoolId",
            value=api_user_pool.user_pool_id,
        )
        CfnOutput(
            self,
            "ApiOAuthClientId",
            value=api_client.user_pool_client_id,
        )
        CfnOutput(
            self,
            "ApiOAuthTokenEndpoint",
            value=f"{api_domain.base_url()}/oauth2/token",
        )
        CfnOutput(
            self,
            "ApiOAuthScope",
            value=f"{resource_prefix}/score",
        )
        if verification_client is not None:
            CfnOutput(
                self,
                "ApiOAuthDeniedScopeClientId",
                value=verification_client.user_pool_client_id,
            )
            CfnOutput(
                self,
                "ApiOAuthDeniedScope",
                value=f"{resource_prefix}/{verification_scope_name}",
            )
        CfnOutput(
            self,
            "ApiFunctionName",
            value=self.api_function.function_name,
            export_name=f"{resource_prefix}-api-{environment}-function-name",
        )
        CfnOutput(
            self,
            "ResponseWorkerFunctionName",
            value=self.response_worker_function.function_name,
            export_name=(
                f"{resource_prefix}-response-worker-{environment}-function-name"
            ),
        )
        CfnOutput(
            self,
            "AsyncStateTableName",
            value=async_state_table.table_name,
            export_name=f"{resource_prefix}-async-state-{environment}-table-name",
        )

    def _resolve_bucket_parameters(
        self,
        bucket_parameters: Mapping[str, str],
    ) -> dict[str, str]:
        return {
            bucket_id: ssm.StringParameter.value_for_string_parameter(
                self,
                parameter_name,
            )
            for bucket_id, parameter_name in bucket_parameters.items()
        }

    def _grant_s3_access(
        self,
        *,
        functions: Sequence[lambda_.IFunction],
        read_buckets: dict[str, str],
        read_write_buckets: dict[str, str],
    ) -> None:
        buckets = read_buckets | read_write_buckets
        for bucket_id, bucket_name in buckets.items():
            bucket = s3.Bucket.from_bucket_name(
                self,
                f"{bucket_id}Bucket",
                bucket_name,
            )
            for function in functions:
                function.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=[
                            "s3:GetBucketLocation",
                            "s3:ListBucket",
                            "s3:ListBucketMultipartUploads",
                        ],
                        resources=[bucket.bucket_arn],
                    )
                )
                object_actions = ["s3:GetObject", "s3:GetObjectVersion"]
                if bucket_id in read_write_buckets:
                    object_actions.extend(
                        [
                            "s3:AbortMultipartUpload",
                            "s3:ListMultipartUploadParts",
                            "s3:PutObject",
                        ]
                    )
                function.add_to_role_policy(
                    iam.PolicyStatement(
                        actions=object_actions,
                        resources=[bucket.arn_for_objects("*")],
                    )
                )
