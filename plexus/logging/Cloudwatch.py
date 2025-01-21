import boto3
import logging
from botocore.exceptions import ClientError
import os

class CloudWatchLogger:
    def __init__(self, namespace="Plexus"):
        self.namespace = namespace
        self.cloudwatch_client = None
        
        # Debug logging for AWS credentials
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_REGION_NAME')
        
        logging.debug(f"AWS Credentials Check - Access Key: {'Present' if aws_access_key else 'Missing'}, "
                     f"Secret Key: {'Present' if aws_secret_key else 'Missing'}, "
                     f"Region: {'Present' if aws_region else 'Missing'}")
        
        if aws_access_key and aws_secret_key and aws_region:
            try:
                self.cloudwatch_client = boto3.client('cloudwatch', 
                                                    region_name=aws_region,
                                                    aws_access_key_id=aws_access_key,
                                                    aws_secret_access_key=aws_secret_key)
                logging.debug("Successfully initialized CloudWatch client")
            except Exception as e:
                logging.error(f"Failed to initialize CloudWatch client: {str(e)}")
        else:
            logging.warning("CloudWatch client not initialized due to missing credentials")

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

