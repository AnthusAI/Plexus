"""
The Plexus data packages are for loading and caching data for use in training and evaluating scores.
The abstract base class `DataCache` defines the interface for the various data cache implementations.
Each should override the parameters to define whatever parameters it needs, and then implement the `load_data` method to load a dataframe from the cache.
"""
from .DataCache import DataCache
from .AWSDataLakeCache import AWSDataLakeCache
from .CallCriteriaDBCache import CallCriteriaDBCache