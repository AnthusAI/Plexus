"""Shared VPC primitive; service stacks add their own endpoints and policies."""

from __future__ import annotations

from collections.abc import Sequence

from aws_cdk import RemovalPolicy, aws_ec2 as ec2, aws_logs as logs
from constructs import Construct


def build_service_vpc(
    scope: Construct,
    *,
    cidr: str,
    max_azs: int,
    availability_zones: Sequence[str] | None,
    nat_gateways: int,
    subnet_configuration: Sequence[ec2.SubnetConfiguration],
    nat_gateway_provider: ec2.NatProvider | None = None,
    flow_log_group_name: str | None = None,
    vpc_name: str | None = None,
) -> tuple[ec2.Vpc, logs.LogGroup]:
    """Create only generic network primitives under stable caller-owned paths."""

    flow_log_group = logs.LogGroup(
        scope,
        "VpcFlowLogGroup",
        log_group_name=flow_log_group_name,
        retention=logs.RetentionDays.THREE_MONTHS,
        removal_policy=RemovalPolicy.RETAIN,
    )
    vpc = ec2.Vpc(
        scope,
        "Vpc",
        vpc_name=vpc_name,
        ip_addresses=ec2.IpAddresses.cidr(cidr),
        availability_zones=list(availability_zones) if availability_zones else None,
        max_azs=None if availability_zones else max_azs,
        nat_gateways=nat_gateways,
        nat_gateway_provider=nat_gateway_provider,
        restrict_default_security_group=True,
        subnet_configuration=list(subnet_configuration),
        flow_logs={
            "VpcFlowLogs": ec2.FlowLogOptions(
                destination=ec2.FlowLogDestination.to_cloud_watch_logs(flow_log_group),
                traffic_type=ec2.FlowLogTrafficType.ALL,
            )
        },
    )
    return vpc, flow_log_group
