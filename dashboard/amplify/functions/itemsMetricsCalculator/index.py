import os
import json
from plexus.metrics.calculator import MetricsCalculator

def handler(event, context):
    """
    AWS Lambda handler for calculating item and score result metrics.

    This function is invoked by a proxy Lambda resolver attached to the
    `getItemsMetrics` GraphQL query. It receives the query arguments,
    instantiates a MetricsCalculator, and returns the calculated metrics.
    """
    print(f"Received event: {json.dumps(event, indent=2)}")

    # The event payload is the "arguments" object from the AppSync event
    args = event
    account_id = args.get("accountId")
    hours = args.get("hours")
    bucket_minutes = args.get("bucketMinutes")

    if not account_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "accountId is a required argument."}),
        }
    
    # Environment variables are set by the CDK stack
    api_url = os.environ.get("PLEXUS_API_URL")
    api_key = os.environ.get("PLEXUS_API_KEY")

    if not api_url or not api_key:
        print("Error: PLEXUS_API_URL and PLEXUS_API_KEY environment variables must be set.")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Lambda function is not configured correctly."}),
        }

    try:
        # Initialize the calculator with credentials from the environment
        calculator = MetricsCalculator(
            graphql_endpoint=api_url,
            api_key=api_key,
        )

        # Get items and score results summaries
        # Note: bucket_minutes parameter is not supported by these methods
        # They use fixed 1-hour buckets
        items_summary = calculator.get_items_summary(account_id, hours or 24)
        score_results_summary = calculator.get_score_results_summary(account_id, hours or 24)

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

        print(f"Successfully calculated metrics: {json.dumps(metrics, indent=2)}")

        # The Lambda proxy integration expects a JSON-serializable object.
        # The calling TypeScript resolver will parse this.
        return metrics

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        # Propagate a descriptive error back to the caller
        raise Exception(f"Failed to calculate metrics: {str(e)}")
