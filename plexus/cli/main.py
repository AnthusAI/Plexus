import os
from plexus.metrics_calculator import MetricsCalculator

if results:
    # This is the original block for handling 'plexus count results'
    calculator = MetricsCalculator(
        endpoint=os.getenv("PLEXUS_API_URL"), api_key=os.getenv("PLEXUS_API_KEY")
    )
    summary = calculator.get_score_results_summary(hours=hours)
    calculator.display_summary(summary)

elif items:
    # This is the original block for handling 'plexus count items'
    calculator = MetricsCalculator(
        endpoint=os.getenv("PLEXUS_API_URL"), api_key=os.getenv("PLEXUS_API_KEY")
    )
    summary = calculator.get_items_summary(hours=hours)
    calculator.display_summary(summary) 