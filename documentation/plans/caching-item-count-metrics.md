# Caching Strategy for Item Count Metrics

This document outlines a caching strategy to optimize the calculation of item and score result count metrics. The goal is to reduce the number of queries to the backend by caching counts in small, time-aligned buckets.

## 1. Caching Mechanism

- **Cache Granularity:** The core of the caching mechanism will be 5-minute, clock-aligned time buckets.
- **Bucket Alignment:** These buckets will align with the clock, starting at `:00`, `:05`, `:10`, etc., for every hour. For example, `10:00:00 - 10:04:59`.
- **Cached Data:** The cache will store the total count of items and score results for each 5-minute bucket. We will not cache the individual item IDs, only the aggregate counts.
- **Cache Storage:** Initially, an in-memory dictionary will be used for the cache. This can be extended to a more persistent store like Redis or a DynamoDB table in the future.

## 2. Configurable Bucket Width
The width of the cache buckets will be configurable.
- **Default Width:** The default width will be 5 minutes.
- **Configuration:** This will be a parameter in the `MetricsCalculator` class, making it easy to adjust for different performance needs (e.g., switching to 1-minute buckets).

## 3. Cache Storage: SQLite
To provide persistence for local development and CLI tools, the caching mechanism will be updated to use a local SQLite database.

- **Database File:** The cache will be stored in a local SQLite file (e.g., `tmp/metrics_cache.db`).
- **Cache Table:** A simple table will be created to store the cache keys and their corresponding counts.
- **Future Migration:** This SQLite implementation is an intermediate step. It is designed to be easily replaced with a more robust, shared caching solution at the API level (e.g., using DynamoDB) in the future.

## 4. Querying and Caching Logic

The primary analysis will continue to be performed on hourly buckets relative to the current time (e.g., the last hour, the hour before that). However, the data for these hourly buckets will be assembled using the cached buckets.

### Algorithm

For each hourly analysis bucket:

1.  **Identify Sub-Buckets:** Determine the set of 5-minute, clock-aligned buckets that are fully contained within the hourly bucket's time range.

2.  **Handle Overlaps:** The start and end times of the hourly bucket will likely not align perfectly with the 5-minute clock buckets. This creates two "partial" or "overlap" periods:
    *   One at the beginning of the hourly bucket.
    *   One at the end of the hourly bucket.

3.  **Fetch from Cache:**
    *   For each of the fully-contained 5-minute buckets, check if its count is already in the cache.
    *   If a bucket's count is **not** in the cache, perform a GraphQL query to fetch the count for that 5-minute interval.
    *   Store the newly fetched count in the cache for future use.

4.  **Query Overlaps:**
    *   Perform two separate, precise GraphQL queries for the small, non-aligned overlap periods at the start and end of the hourly bucket. These overlap periods will always be less than 5 minutes long. The results of these queries will not be cached.

5.  **Calculate Total:** The total count for the hourly analysis bucket is the sum of:
    *   The counts from all the fully-contained 5-minute buckets (retrieved from the cache or newly fetched).
    *   The counts from the two overlap queries.

## 5. Implementation Plan

-   **Location:** The new logic will be implemented within the `MetricsCalculator` class in `plexus/utils/metrics_calculator.py`.
-   **Helper Functions:**
    *   A function to calculate the 5-minute clock-aligned buckets for a given time range.
    *   A function to manage cache lookups, fetching from the database, and storing new entries in the cache.
-   **Testing:** The `test_metrics_calculator.py` will be updated to include tests for the caching logic, ensuring that it correctly calculates totals and handles cache hits and misses. 