"""
Simple Python resolver for calculating items metrics.
This replaces the complex standalone CDK Lambda with a simple Amplify function.
"""

import os
import json
import logging
import sys
from pathlib import Path

# Add the plexus module to the path
# The plexus module will be copied during the build process
sys.path.insert(0, str(Path(__file__).parent))

from plexus.metrics.calculator import create_calculator_from_env

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Simple Python resolver for items metrics calculation.
    
    This function uses the Amplify-provided environment variables and
    the lightweight plexus.metrics.calculator module.
    """
    try:
        logger.info(f"Python resolver invoked with event: {json.dumps(event)}")
        
        # Extract arguments from the AppSync event
        arguments = event.get('arguments', {})
        account_id = arguments.get('accountId')
        hours = arguments.get('hours', 24)
        bucket_minutes = arguments.get('bucketMinutes', 60)
        
        if not account_id:
            raise ValueError("Missing required parameter: accountId")
        
        logger.info(f"Calculating metrics for account {account_id} over {hours} hours")
        
        # Create calculator using Amplify environment variables
        # The create_calculator_from_env function will automatically use:
        # - API_PLEXUSDASHBOARD_GRAPHQLAPIENDPOINTOUTPUT (GraphQL endpoint)
        # - API_PLEXUSDASHBOARD_GRAPHQLAPIKEYOUTPUT (API key)
        calculator = create_calculator_from_env()
        
        # Get metrics using the lightweight calculator
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

        # Return the metrics directly (no need for statusCode/body wrapper)
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
        return metrics
        
    except Exception as e:
        logger.error(f"Error calculating metrics: {str(e)}")
        raise e  # Let AppSync handle the error response 