import boto3
import logging
from botocore.exceptions import ClientError
import os

class CloudWatchLogger:
    def __init__(self, namespace="Plexus"):
        self.namespace = namespace
        self.cloudwatch_client = None

        # Get AWS region
        aws_region = os.getenv('AWS_REGION') or os.getenv('AWS_REGION_NAME') or os.getenv('AWS_DEFAULT_REGION')

        if not aws_region:
            logging.warning("AWS region not set, CloudWatch metrics disabled")
            return

        # Check if we're running in Lambda (should always use IAM role)
        is_lambda = os.getenv('AWS_EXECUTION_ENV') or os.getenv('AWS_LAMBDA_FUNCTION_NAME')

        try:
            # In Lambda, always use IAM role (never explicit credentials)
            # In EC2, use explicit credentials if provided, otherwise use instance profile
            if is_lambda:
                logging.info("Running in Lambda - using IAM role credentials")
                self.cloudwatch_client = boto3.client('cloudwatch', region_name=aws_region)
            else:
                # Check if explicit credentials are provided (EC2 workers)
                aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
                aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')

                if aws_access_key and aws_secret_key:
                    logging.info("Using explicit AWS credentials from environment")
                    self.cloudwatch_client = boto3.client('cloudwatch',
                                                        region_name=aws_region,
                                                        aws_access_key_id=aws_access_key,
                                                        aws_secret_access_key=aws_secret_key)
                else:
                    logging.info("Using default AWS credentials (IAM role/instance profile)")
                    self.cloudwatch_client = boto3.client('cloudwatch', region_name=aws_region)

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
                'Dimensions': [{'Name': k, 'Value': str(v)} for k, v in dimensions.items()]
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

