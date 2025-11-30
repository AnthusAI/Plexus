"""
DatasetCache - loads datasets from the Plexus API and S3 storage.

This cache downloads dataset files (Parquet/CSV) from S3 using metadata
from the Plexus API. It uses DatasetResolver from report blocks for
consistent caching behavior.
"""

import asyncio
import logging
import pandas as pd
from pydantic import Field
from typing import Optional

from plexus.data.DataCache import DataCache

logger = logging.getLogger(__name__)


class DatasetCache(DataCache):
    """
    DataCache implementation that loads datasets from the Plexus API and S3.

    This cache uses DatasetResolver (from report blocks) internally to provide
    consistent dataset caching across all Plexus functionality.

    Usage in score configuration:
        data:
          class: DatasetCache
          data_source_key: "my-dataset-key"

    Or override via CLI:
        plexus train --source "my-dataset-key" ...
    """

    class Parameters(DataCache.Parameters):
        """Parameters for DatasetCache."""

        # Generic identifiers - DatasetResolver will try ID, key, then name
        source: Optional[str] = Field(
            default=None,
            description="DataSource identifier (ID, key, or name) - uses latest dataset from source"
        )
        dataset: Optional[str] = Field(
            default=None,
            description="Dataset ID - uses specific dataset"
        )

    def __init__(self, **parameters):
        """Initialize DatasetCache."""
        super().__init__(**parameters)

        # Validate that at least one identifier is provided
        if not (self.parameters.source or self.parameters.dataset):
            raise ValueError("Must provide either 'source' (data source identifier) or 'dataset' (dataset ID)")

        logger.info(f"Initializing DatasetCache with source={self.parameters.source}, dataset={self.parameters.dataset}")

    def load_dataframe(self, *, data=None, fresh=False):
        """
        Load dataset from API/S3 into a DataFrame.

        Uses DatasetResolver from report blocks for consistent caching.

        Args:
            data: Optional dict containing parameters (uses self.parameters if not provided)
            fresh: If True, bypass cache and download fresh

        Returns:
            pd.DataFrame: The loaded dataset
        """
        from plexus.dashboard.api.client import PlexusDashboardClient
        from plexus.reports.blocks.data_utils import DatasetResolver

        logger.info(f"Loading dataset from API/S3 using DatasetResolver")

        # Initialize API client and resolver
        client = PlexusDashboardClient()
        resolver = DatasetResolver(client)

        # Use DatasetResolver to get cached file path
        # DatasetResolver handles identifier resolution (ID, key, or name)
        async def _resolve():
            return await resolver.resolve_and_cache_dataset(
                source=self.parameters.source,
                dataset=self.parameters.dataset,
                fresh=fresh
            )

        # Run async function
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            if loop.is_running():
                # If we're already in an async context, nest it
                import nest_asyncio
                nest_asyncio.apply()
                local_path, metadata = loop.run_until_complete(_resolve())
            else:
                local_path, metadata = loop.run_until_complete(_resolve())
        except Exception as e:
            raise ValueError(f"Failed to resolve dataset: {str(e)}")

        if not local_path:
            raise ValueError("DatasetResolver returned no path")

        logger.info(f"Dataset cached at: {local_path}")
        logger.info(f"Dataset metadata: {metadata}")

        # Load from cached file
        if local_path.endswith('.parquet'):
            df = pd.read_parquet(local_path)
        elif local_path.endswith('.csv'):
            df = pd.read_csv(local_path)
        else:
            raise ValueError(f"Unsupported file type: {local_path}")

        logger.info(f"Dataset loaded: {df.shape[0]} rows x {df.shape[1]} columns")
        logger.info(f"Columns: {df.columns.tolist()}")

        return df
