"""Deploy stable command-service foundations before their Amplify environment."""

import os

import aws_cdk as cdk

from plexus.infrastructure.service_network import (
    ServiceNetworkFoundationStack,
    resolve_service_network_environment,
)

app = cdk.App()
environment = os.environ.get("PLEXUS_COMMAND_SERVICE_ENVIRONMENT", "")
settings = resolve_service_network_environment(environment)
normalized_environment = settings.environment
ServiceNetworkFoundationStack(
    app,
    f"CommandServiceFoundation{normalized_environment.title()}",
    service_prefix=os.environ.get("PLEXUS_SERVICE_PREFIX", "plexus"),
    environment=environment,
    amplify_deployment_role_arn=os.environ.get(
        "PLEXUS_AMPLIFY_DEPLOYMENT_ROLE_ARN", ""
    ),
    stack_name=f"plexus-command-service-foundation-{normalized_environment}",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION"),
    ),
)
app.synth()
