import boto3
import logging
from botocore.exceptions import ClientError
import os
from plexus.logging.redaction import redact_text

class CloudWatchLogger:
    _shared_clients = {}

    def __init__(self, namespace="Plexus"):
        self.namespace = namespace
        self.cloudwatch_client = None

        # Get AWS region
        aws_region = os.getenv('AWS_REGION_NAME') or os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION')

        if not aws_region:
            logging.warning("AWS region not set, CloudWatch metrics disabled")
            return

        try:
            cache_key = (
                aws_region,
                id(boto3.client),
            )
            cached_client = self._shared_clients.get(cache_key)
            if cached_client is not None:
                self.cloudwatch_client = cached_client
                logging.debug(f"Reusing cached CloudWatch client in region {aws_region}")
                return

            logging.info("Using default AWS credentials for CloudWatch metrics")
            self.cloudwatch_client = boto3.client('cloudwatch', region_name=aws_region)

            self._shared_clients[cache_key] = self.cloudwatch_client
            logging.info(f"Successfully initialized CloudWatch client in region {aws_region}")
        except Exception as e:
            logging.error(f"Failed to initialize CloudWatch client: {str(e)}")

    def log_metric(self, metric_name, metric_value, dimensions):
        """
        Log a metric to CloudWatch with the specified dimensions.
        
        Args:
            metric_name (str): Name of the metric
            metric_value (float): Value of the metric
            dimensions (dict): Dictionary of dimension names and values
        """
        if not self.cloudwatch_client:
            logging.warning(f"CloudWatch not configured, skipping metric: {metric_name}")
            return

        try:
            logging.debug(f"Attempting to log metric to CloudWatch - Name: {metric_name}, Value: {metric_value}")
            metric_data = {
                'MetricName': metric_name,
                'Value': float(metric_value),
                'Unit': 'None',
                'Dimensions': [
                    {'Name': redact_text(str(k)), 'Value': redact_text(str(v))}
                    for k, v in dimensions.items()
                ]
            }
            logging.debug(f"Prepared metric data: {metric_data}")

            self.cloudwatch_client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )
            logging.debug(f"Successfully logged {metric_name} to CloudWatch with dimensions: {dimensions}")
        except ClientError as e:
            logging.error(f"Failed to log metric to CloudWatch: {e}")
            if hasattr(e, 'response'):
                logging.error(f"Error response: {e.response}")
        except Exception as e:
            logging.error(f"Unexpected error logging metric to CloudWatch: {str(e)}")
