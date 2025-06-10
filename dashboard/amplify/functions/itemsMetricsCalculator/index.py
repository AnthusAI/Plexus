import os
import json
import logging
import sys
from pathlib import Path

# Add the bundled plexus module to the path
sys.path.insert(0, str(Path(__file__).parent))

from plexus.metrics.calculator import create_calculator_from_env

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    AWS Lambda handler for calculating items metrics.
    This function is invoked by a resolver and uses the Plexus metrics module.
    """
    try:
        logger.info(f"Lambda function invoked with event: {json.dumps(event)}")
        
        # The actual arguments are passed directly in the event payload
        # from the upstream AppSync resolver.
        account_id = event.get('accountId')
        if not account_id:
            raise ValueError("Missing required parameter: accountId")
        
        hours = event.get('hours', 24)
        logger.info(f"Calculating metrics for account {account_id} over {hours} hours")
        
        # Create calculator using environment variables provided by the CDK stack
        calculator = create_calculator_from_env()
        
        # Get metrics summaries
        items_summary = calculator.get_items_summary(account_id, hours)
        score_results_summary = calculator.get_score_results_summary(account_id, hours)
        
        # Merge the chart data for the combined response
        chart_data = []
        item_chart_map = {item['bucketStart']: item['items'] for item in items_summary['chartData']}
        
        for sr_bucket in score_results_summary['chartData']:
            bucket_start = sr_bucket['bucketStart']
            chart_data.append({
                'time': sr_bucket['time'],
                'items': item_chart_map.get(bucket_start, 0),
                'scoreResults': sr_bucket['scoreResults'],
                'bucketStart': bucket_start,
                'bucketEnd': sr_bucket['bucketEnd']
            })

        metrics = {
            'itemsPerHour': items_summary['itemsPerHour'],
            'itemsAveragePerHour': items_summary['itemsAveragePerHour'],
            'itemsPeakHourly': items_summary['itemsPeakHourly'],
            'itemsTotal24h': items_summary['itemsTotal24h'],
            'scoreResultsPerHour': score_results_summary['scoreResultsPerHour'],
            'scoreResultsAveragePerHour': score_results_summary['scoreResultsAveragePerHour'],
            'scoreResultsPeakHourly': score_results_summary['scoreResultsPeakHourly'],
            'scoreResultsTotal24h': score_results_summary['scoreResultsTotal24h'],
            'chartData': chart_data
        }
        
        logger.info("Metrics calculated successfully")
        # Return the raw JSON object, the resolver will handle the response format
        return metrics
        
    except Exception as e:
        logger.error(f"Error calculating metrics: {str(e)}")
        # Re-raise the exception to be handled by the AppSync resolver
        raise e 