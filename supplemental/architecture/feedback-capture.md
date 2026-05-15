# Understanding the Feedback Capture Process

This document outlines the process by which the `commands/data/feedback/capture.py` script extracts a history of edits from the Call Criteria database and consolidates them into single "feedback" records for analysis in an external system.

## 1. Data Aggregation from Change Logs

The process begins by querying three distinct change log tables in the Call Criteria database: `ResponseChangeLog`, `ScoreChangeLog`, and `CalibrationChangeLog`.

These queries select records based on a specific Call Criteria `scorecard_id` and a date range. If a specific `question_id` is provided, the queries are further filtered to that scope.

Conceptually, this step is equivalent to a `UNION ALL` operation, gathering all raw change events from these three sources into a single, in-memory collection.

## 2. Grouping Changes by Form and Question

Once the raw change logs are in memory, they are grouped by a composite key of `(form_id, question_id)`.

This creates a map where each key corresponds to a unique answer on a specific form, and the value is a list of all the change events that occurred for that answer.

Within each group, the list of change events is then sorted chronologically based on the `changed_at` timestamp. This step is critical as it establishes the precise timeline of edits for each individual answer.

## 3. Reconstructing the "Before" and "After" State

With a chronologically sorted history for each `(form_id, question_id)` pair, the script reconstructs the state of the answer before and after all edits took place.

-   The **initial answer** is determined by iterating forward through the sorted changes and selecting the first non-null `original_answer_text` it encounters. This is analogous to a `FIRST_VALUE(...) IGNORE NULLS` SQL window function.
-   The **final answer** is determined by iterating backward through the sorted changes and selecting the first non-null `new_answer_text`. This is analogous to a `LAST_VALUE(...) IGNORE NULLS` SQL window function.
-   The same logic is applied to the comment fields to determine the initial and final comments associated with the answer.

### Potential for Brittleness

This method of determining the initial and final state is dependent on the completeness and consistency of the log data. If the very first change record in the timeline has a null `original_answer_text`, or if intermediate records have inconsistent data, the reconstructed "before" and "after" states may not accurately reflect the true history of the edit.

## 4. Synchronizing with the External System

The final step is to save this consolidated "edit event" to the external system. This is performed as a `MERGE`-like operation: if a record for this event already exists, it is updated; otherwise, a new one is inserted. The logic for identifying an existing record to prevent duplicates is multifaceted.

### Initial Match Attempt

The primary method for finding a duplicate involves a lookup based on a composite key that includes the Call Criteria `form_id`. This is generally a reliable approach.

### Fallback Matching Logic

If a precise match is not found using the primary method, the script employs fallback strategies. One such strategy involves matching records based on their relative position within a batch. For example, if the script is processing 10 records and finds 10 existing records in the destination system for the same scorecard, it may assume the first record in its batch corresponds to the first one from the database, the second to the second, and so on.

### Potential for Brittleness

This positional matching fallback is highly fragile. It relies on the assumption that the order of records retrieved from the destination system is identical to the order in which the script is processing them. Any discrepancy in ordering can lead to records being mismatched, causing an `UPDATE` intended for one `form_id` to be incorrectly applied to another. This is a significant area for investigation when diagnosing data inconsistencies. 