import os
import json
import logging
import sys

# Add the current directory to the path so we can import the plexus module
sys.path.insert(0, os.path.dirname(__file__))

from plexus.utils.metrics_calculator import create_calculator_from_env

# Set up basic logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    AWS Lambda handler for calculating items metrics.
    
    This function calculates comprehensive metrics for items and score results
    over the last 24 hours (or specified timeframe) using the factored-out
    MetricsCalculator class.
    
    Event structure:
    {
        "accountId": "string",           # Required: Account ID to calculate metrics for
        "hours": 24                      # Optional: Number of hours to look back (default: 24)
    }
    
    Environment variables required:
    - PLEXUS_API_URL: GraphQL API endpoint
    - PLEXUS_API_KEY: API key for authentication
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "itemsPerHour": 15,
            "itemsAveragePerHour": 12.5,
            "itemsPeakHourly": 20,
            "itemsTotal24h": 300,
            "scoreResultsPerHour": 45,
            "scoreResultsAveragePerHour": 38.2,
            "scoreResultsPeakHourly": 60,
            "scoreResultsTotal24h": 917,
            "chartData": [
                {
                    "time": "3 pm",
                    "items": 15,
                    "scoreResults": 45,
                    "bucketStart": "2024-01-01T15:00:00Z",
                    "bucketEnd": "2024-01-01T16:00:00Z"
                }
                // ... more hourly data
            ]
        }
    }
    """
    try:
        logger.info(f"Lambda function invoked with event: {json.dumps(event)}")
        
        # Parse input
        account_id = event.get('accountId')
        if not account_id:
            logger.error("Missing required parameter: accountId")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required parameter: accountId'
                })
            }
        
        hours = event.get('hours', 24)
        logger.info(f"Calculating metrics for account {account_id} over {hours} hours")
        
        # Create calculator and get metrics using the new summary functions
        calculator = create_calculator_from_env()
        
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
        return {
            'statusCode': 200,
            'body': json.dumps(metrics)
        }
        
    except Exception as e:
        logger.error(f"Error calculating metrics: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Internal server error: {str(e)}'
            })
        } 