import boto3
import logging
from botocore.exceptions import ClientError
import os

class CloudWatchLogger:
    def __init__(self, namespace="Plexus"):
        self.namespace = namespace
        self.cloudwatch_client = None
        if os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY') \
                and os.getenv('AWS_DEFAULT_REGION'):
            self.cloudwatch_client = boto3.client('cloudwatch')

    def log_metric(self, metric_name, metric_value, dimensions):
        """
        Log a metric to CloudWatch with the specified dimensions.
        
        Args:
            metric_name (str): Name of the metric
            metric_value (float): Value of the metric
            dimensions (dict): Dictionary of dimension names and values
        """
        if not self.cloudwatch_client:
            logging.debug(f"CloudWatch not configured, skipping metric: {metric_name}")
            return

        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': float(metric_value),
                'Unit': 'None',
                'Dimensions': [{'Name': k, 'Value': str(v)} for k, v in dimensions.items()]
            }

            self.cloudwatch_client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )
            logging.debug(f"Successfully logged {metric_name} to CloudWatch with dimensions: {dimensions}")
        except ClientError as e:
            logging.error(f"Failed to log metric to CloudWatch: {e}")

