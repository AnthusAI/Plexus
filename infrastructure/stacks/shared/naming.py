"""
Centralized naming utilities for Plexus infrastructure resources.

Naming convention: plexus-{service}-{environment}-{resource}
Examples:
  - plexus-scoring-staging-queue
  - plexus-scoring-production-dlq
  - plexus-monitoring-staging-dashboard
"""

def get_resource_name(service: str, environment: str, resource: str) -> str:
    """
    Generate a standardized resource name.

    Args:
        service: Service name (e.g., 'scoring', 'monitoring')
        environment: Environment name ('staging' or 'production')
        resource: Resource type (e.g., 'queue', 'dlq', 'topic')

    Returns:
        Formatted resource name following Plexus naming convention
    """
    return f"plexus-{service}-{environment}-{resource}"
