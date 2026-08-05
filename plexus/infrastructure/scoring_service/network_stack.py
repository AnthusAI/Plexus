from __future__ import annotations

from collections.abc import Sequence

from aws_cdk import (
    CfnOutput,
    RemovalPolicy,
    Stack,
    Tags,
    aws_ec2 as ec2,
    aws_logs as logs,
)
from constructs import Construct


class ScoringServiceNetworkStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        resource_prefix: str,
        display_name: str,
        environment: str,
        cidr: str = "10.42.0.0/16",
        max_azs: int = 2,
        availability_zones: Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if not resource_prefix.strip():
            raise ValueError("resource_prefix must not be empty")
        if not display_name.strip():
            raise ValueError("display_name must not be empty")

        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Service", resource_prefix)
        Tags.of(self).add("Environment", environment)

        az_count = len(availability_zones) if availability_zones else max_azs

        nat_eips = [
            self._create_nat_eip(
                az_index=az_index,
                environment=environment,
                resource_prefix=resource_prefix,
            )
            for az_index in range(1, az_count + 1)
        ]

        flow_log_group = logs.LogGroup(
            self,
            "VpcFlowLogGroup",
            log_group_name=f"/{resource_prefix}/network/vpc-flow-logs",
            retention=logs.RetentionDays.THREE_MONTHS,
            removal_policy=RemovalPolicy.RETAIN,
        )

        vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name=f"{resource_prefix}-vpc",
            ip_addresses=ec2.IpAddresses.cidr(cidr),
            availability_zones=(
                list(availability_zones) if availability_zones else None
            ),
            max_azs=None if availability_zones else max_azs,
            nat_gateways=az_count,
            nat_gateway_provider=ec2.NatProvider.gateway(
                eip_allocation_ids=[nat_eip.attr_allocation_id for nat_eip in nat_eips]
            ),
            restrict_default_security_group=True,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="private-egress",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
            flow_logs={
                "VpcFlowLogs": ec2.FlowLogOptions(
                    destination=ec2.FlowLogDestination.to_cloud_watch_logs(
                        flow_log_group
                    ),
                    traffic_type=ec2.FlowLogTrafficType.ALL,
                )
            },
        )

        endpoint_security_group = ec2.SecurityGroup(
            self,
            "VpcEndpointSecurityGroup",
            vpc=vpc,
            security_group_name=f"{resource_prefix}-vpc-endpoints",
            description="Allow private subnets to reach AWS interface endpoints",
            allow_all_outbound=False,
        )
        endpoint_security_group.add_ingress_rule(
            ec2.Peer.ipv4(cidr),
            ec2.Port.tcp(443),
            f"HTTPS from {display_name} VPC",
        )

        self._add_gateway_endpoints(vpc)
        self._add_interface_endpoints(
            vpc=vpc,
            endpoint_security_group=endpoint_security_group,
        )

        CfnOutput(
            self,
            "VpcId",
            value=vpc.vpc_id,
            export_name=f"{resource_prefix}-vpc-id",
        )
        for az_index, nat_eip in enumerate(nat_eips, start=1):
            CfnOutput(
                self,
                f"NatGateway{az_index}PublicIp",
                value=nat_eip.ref,
                export_name=f"{resource_prefix}-nat-gateway-{az_index}-public-ip",
            )
            CfnOutput(
                self,
                f"NatGateway{az_index}AllocationId",
                value=nat_eip.attr_allocation_id,
                export_name=(
                    f"{resource_prefix}-nat-gateway-{az_index}-allocation-id"
                ),
            )

        self.vpc = vpc
        self.endpoint_security_group = endpoint_security_group
        self.nat_eips = nat_eips
        self.flow_log_group = flow_log_group
        self.nat_gateway_ids = [
            resource.ref
            for resource in sorted(
                (
                    child
                    for child in vpc.node.find_all()
                    if isinstance(child, ec2.CfnNatGateway)
                ),
                key=lambda resource: resource.node.path,
            )
        ]

    def _create_nat_eip(
        self,
        *,
        az_index: int,
        environment: str,
        resource_prefix: str,
    ) -> ec2.CfnEIP:
        nat_eip = ec2.CfnEIP(
            self,
            f"NatGateway{az_index}ElasticIp",
            domain="vpc",
        )
        nat_eip.apply_removal_policy(RemovalPolicy.RETAIN)
        Tags.of(nat_eip).add("Name", f"{resource_prefix}-nat-{az_index}-eip")
        Tags.of(nat_eip).add("Environment", environment)
        Tags.of(nat_eip).add("Purpose", "sql-allowlist-egress")
        return nat_eip

    def _add_gateway_endpoints(self, vpc: ec2.Vpc) -> None:
        vpc.add_gateway_endpoint(
            "S3GatewayEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            ],
        )
        vpc.add_gateway_endpoint(
            "DynamoDbGatewayEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            subnets=[
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
                ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            ],
        )

    def _add_interface_endpoints(
        self,
        *,
        vpc: ec2.Vpc,
        endpoint_security_group: ec2.ISecurityGroup,
    ) -> None:
        endpoint_subnets = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        )
        endpoint_services = {
            "CloudWatchLogsEndpoint": (
                ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS
            ),
            "CloudWatchMonitoringEndpoint": (
                ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_MONITORING
            ),
            "SecretsManagerEndpoint": ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            "SsmEndpoint": ec2.InterfaceVpcEndpointAwsService.SSM,
            "SqsEndpoint": ec2.InterfaceVpcEndpointAwsService.SQS,
        }

        for construct_id, service in endpoint_services.items():
            vpc.add_interface_endpoint(
                construct_id,
                service=service,
                open=False,
                private_dns_enabled=True,
                security_groups=[endpoint_security_group],
                subnets=endpoint_subnets,
            )
