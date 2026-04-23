#!/usr/bin/env python3
"""
Dataset tools for Plexus MCP Server
"""
import os
import sys
import logging
import json
from typing import Dict, Any, Union, Optional, List
from io import StringIO
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_dataset_tools(mcp: FastMCP):
    """Register dataset tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_dataset_load(
        source_identifier: str,
        fresh: bool = False
    ) -> str:
        """
        Load a dataset from a DataSource using the existing CLI functionality.
        
        This tool reuses the core dataset loading logic from the CLI command to ensure DRY principles.
        It loads a dataframe from the specified data source, generates a Parquet file,
        and creates a new DataSet record in the database.
        
        Parameters:
        - source_identifier: Identifier (ID, key, or name) of the DataSource to load
        - fresh: Force a fresh load, ignoring any caches (default: False)
        
        Returns:
        - Status message indicating success/failure and dataset information
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Import the core dataset loading functionality
            try:
                from plexus.cli.dataset.datasets import create_client
                from plexus.cli.shared.identifier_resolution import resolve_data_source
                from plexus.cli.dataset.datasets import create_initial_data_source_version, get_amplify_bucket
                import yaml
                import pandas as pd
                import pyarrow as pa
                import pyarrow.parquet as pq
                from io import BytesIO
                from datetime import datetime, timezone
                import importlib
                import boto3
                from botocore.exceptions import NoCredentialsError
            except ImportError as e:
                return f"Error: Could not import required modules: {e}. Dataset loading functionality may not be available."
            
            # Create client using the existing function
            client = create_client()
            
            # Reuse the core dataset loading logic from DatasetCommands.py
            # This is the exact same logic as in the CLI command's _load() function
            
            # 1. Fetch the DataSource
            logger.info(f"Resolving DataSource with identifier: {source_identifier}")
            data_source = await resolve_data_source(client, source_identifier)
            if not data_source:
                return f"Error: Could not resolve DataSource with identifier: {source_identifier}"
            
            logger.info(f"Found DataSource: {data_source.name} (ID: {data_source.id})")

            # 2. Parse YAML configuration
            if not data_source.yamlConfiguration:
                return f"Error: DataSource '{data_source.name}' has no yamlConfiguration."

            try:
                config = yaml.safe_load(data_source.yamlConfiguration)
            except yaml.YAMLError as e:
                return f"Error parsing yamlConfiguration: {e}"

            if not isinstance(config, dict):
                return f"Error: yamlConfiguration must be a YAML dictionary, but got {type(config).__name__}: {config}"

            # Handle both scorecard format (with 'data' section) and dataset format (direct config)
            data_config = config.get('data')
            if not data_config:
                # Check if this is a direct dataset configuration (recommended format)
                if 'class' in config:
                    logger.info("Detected direct dataset configuration format")
                    
                    # Handle built-in Plexus classes vs client-specific extensions
                    class_name = config['class']
                    if class_name in ['FeedbackItems']:
                        # Built-in Plexus classes (single file modules)
                        class_path = f"plexus.data.{class_name}"
                    else:
                        # Client-specific extensions (existing behavior)
                        class_path = f"plexus_extensions.{class_name}.{class_name}"
                    
                    data_config = {
                        'class': class_path,
                        'parameters': {k: v for k, v in config.items() if k != 'class'}
                    }
                else:
                    return "Error: No 'data' section in yamlConfiguration and no 'class' specified."

            # 3. Dynamically load DataCache class
            data_cache_class_path = data_config.get('class')
            if not data_cache_class_path:
                return "Error: No 'class' specified in data configuration."

            try:
                module_path, class_name = data_cache_class_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                data_cache_class = getattr(module, class_name)
            except (ImportError, AttributeError) as e:
                return f"Error: Could not import data cache class '{data_cache_class_path}': {e}"

            # 4. Load dataframe
            logger.info(f"Loading dataframe using {data_cache_class_path}...")
            data_cache_params = data_config.get('parameters', {})
            data_cache = data_cache_class(**data_cache_params)

            # Pass the parameters to load_dataframe
            dataframe = data_cache.load_dataframe(data=data_cache_params, fresh=fresh)
            logger.info(f"Loaded dataframe with {len(dataframe)} rows and columns: {dataframe.columns.tolist()}")

            # 5. Generate Parquet file in memory
            if dataframe.empty:
                return "Warning: Dataframe is empty, no dataset created."

            logger.info("Generating Parquet file in memory...")
            buffer = BytesIO()
            table = pa.Table.from_pandas(dataframe)
            pq.write_table(table, buffer)
            buffer.seek(0)
            logger.info("Parquet file generated successfully.")

            # 6. Get the current DataSource version and resolve score version
            logger.info("Creating new DataSet record...")
            
            if not hasattr(data_source, 'accountId') or not data_source.accountId:
                return "Error: DataSource is missing accountId. Cannot proceed."
            account_id = data_source.accountId

            # Get the current version of the DataSource, creating one if it doesn't exist
            if not data_source.currentVersionId:
                logger.info("DataSource has no currentVersionId. Creating initial version...")
                data_source_version_id = await create_initial_data_source_version(client, data_source)
                if not data_source_version_id:
                    return "Error: Failed to create initial DataSource version."
            else:
                data_source_version_id = data_source.currentVersionId
                logger.info(f"Using existing DataSource version ID: {data_source_version_id}")

            # Get the score version - use the score linked to the DataSource if available (optional)
            score_version_id = None
            if hasattr(data_source, 'scoreId') and data_source.scoreId:
                logger.info(f"DataSource is linked to score ID: {data_source.scoreId}")
                # Get the champion version of this score
                score_query = client.execute(
                    """
                    query GetScore($id: ID!) {
                        getScore(id: $id) {
                            id
                            name
                            championVersionId
                        }
                    }
                    """,
                    {"id": data_source.scoreId}
                )
                
                if score_query and score_query.get('getScore') and score_query['getScore'].get('championVersionId'):
                    score_version_id = score_query['getScore']['championVersionId']
                    logger.info(f"Using champion version ID: {score_version_id}")
                else:
                    logger.warning(f"Score {data_source.scoreId} has no champion version. Creating DataSet without score version.")
            else:
                logger.info("DataSource is not linked to a specific score. Creating DataSet without score version.")

            # Create a DataSet linked to the DataSource version and optionally to a score version
            dataset_input = {
                "name": f"{data_source.name} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
                "accountId": account_id,
                "dataSourceVersionId": data_source_version_id,
            }
            
            # Add optional fields only if they have values
            if score_version_id:
                dataset_input["scoreVersionId"] = score_version_id
            if hasattr(data_source, 'scorecardId') and data_source.scorecardId:
                dataset_input["scorecardId"] = data_source.scorecardId
            if hasattr(data_source, 'scoreId') and data_source.scoreId:
                dataset_input["scoreId"] = data_source.scoreId
                
            new_dataset_record = client.execute(
                """
                mutation CreateDataSet($input: CreateDataSetInput!) {
                    createDataSet(input: $input) {
                        id
                        name
                        dataSourceVersionId
                        scoreVersionId
                    }
                }
                """,
                {
                    "input": dataset_input
                }
            )
            new_dataset = new_dataset_record['createDataSet']
            new_dataset_id = new_dataset['id']
            
            logger.info(f"Created DataSet record with ID: {new_dataset_id}")

            # 7. Upload Parquet to S3
            file_name = "dataset.parquet"
            s3_key = f"datasets/{account_id}/{new_dataset_id}/{file_name}"
            
            logger.info(f"Uploading Parquet file to S3 at: {s3_key}")
            
            bucket_name = get_amplify_bucket()
            if not bucket_name:
                 logger.error("S3 bucket name not found. Cannot upload file.")
                 client.execute("""
                    mutation UpdateDataSet($input: UpdateDataSetInput!) {
                        updateDataSet(input: $input) { id }
                    }
                 """, {"input": {"id": new_dataset_id, "description": "FAILED: S3 bucket not configured."}})
                 return "Error: S3 bucket name not found. Cannot upload file."

            try:
                s3_client = boto3.client('s3')
                s3_client.upload_fileobj(buffer, bucket_name, s3_key)
                logger.info("File uploaded successfully to S3.")
            except NoCredentialsError:
                return "Error: AWS credentials not found."
            except Exception as e:
                logger.error(f"Failed to upload file to S3: {e}")
                client.execute("""
                   mutation UpdateDataSet($input: UpdateDataSetInput!) {
                       updateDataSet(input: $input) { id }
                   }
                """, {"input": {"id": new_dataset_id, "description": f"FAILED: S3 upload failed: {e}"}})
                return f"Error: Failed to upload file to S3: {e}"

            # 8. Update DataSet with file path
            logger.info(f"Updating DataSet record with file path...")
            client.execute(
                """
                mutation UpdateDataSet($input: UpdateDataSetInput!) {
                    updateDataSet(input: $input) {
                        id
                        file
                    }
                }
                """,
                {
                    "input": {
                        "id": new_dataset_id,
                        "file": s3_key,
                    }
                }
            )
            logger.info("DataSet record updated successfully.")
            
            return f"Successfully loaded dataset '{data_source.name}':\n" + \
                   f"- DataSet ID: {new_dataset_id}\n" + \
                   f"- Rows: {len(dataframe)}\n" + \
                   f"- Columns: {dataframe.columns.tolist()}\n" + \
                   f"- S3 Path: {s3_key}\n" + \
                   f"- Fresh Load: {fresh}"

        except Exception as e:
            logger.error(f"Error in dataset load: {str(e)}", exc_info=True)
            return f"Error loading dataset: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during dataset_load: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_dataset_build_from_feedback_window(
        scorecard: str,
        score: str,
        max_items: int = 100,
        days: Optional[int] = None,
        balance: bool = True,
        score_version_id: Optional[str] = None,
    ) -> str:
        """
        Build a balanced associated dataset from recent qualifying feedback items.

        Creates a deterministic dataset that can be used for reproducible evaluations.
        Uses round-robin class balancing by default to ensure equal representation.

        Parameters:
        - scorecard: Scorecard identifier (id/key/name/external id)
        - score: Score identifier (id/key/name/external id)
        - max_items: Maximum items to include (default: 100). Use 200 for robust regression sets.
        - days: Lookback window in days. If omitted, searches all available feedback history.
        - balance: Apply class balancing via round-robin selection (default: True).
                   Set to False to include more items when feedback is scarce.
        - score_version_id: Optional specific version to use for class label resolution.
                            If omitted, uses the champion version.

        Returns:
        - JSON payload with dataset_id, rows_written, class_distribution_after,
          balance_applied, qualifying_found, and other curation metadata.
        """
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        try:
            try:
                from plexus.cli.dataset.datasets import create_client
                from plexus.cli.dataset.curation import build_associated_dataset_from_feedback_window
                from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier
                from plexus.cli.evaluation.evaluations import validate_dataset_materialization
            except ImportError as exc:
                return f"Error: Could not import required modules: {exc}"

            client = create_client()

            # Resolve scorecard and score to IDs
            scorecard_id = resolve_scorecard_identifier(client, scorecard)
            if not scorecard_id:
                return f"Error: Could not resolve scorecard '{scorecard}'"
            score_id = resolve_score_identifier(client, scorecard_id, score)
            if not score_id:
                return f"Error: Could not resolve score '{score}' in scorecard '{scorecard}'"

            result = build_associated_dataset_from_feedback_window(
                client=client,
                scorecard_id=scorecard_id,
                score_id=score_id,
                max_items=max_items,
                days=days,
                balance=balance,
                class_source_score_version_id=score_version_id or None,
            )
            dataset_id = result.get("dataset_id")
            dataset_file = result.get("dataset_file") or result.get("s3_key")
            readiness = validate_dataset_materialization(
                {
                    "id": dataset_id,
                    "file": dataset_file,
                }
            )
            if not readiness.get("is_materialized"):
                reason = readiness.get("materialization_error") or "unknown"
                return (
                    "Error: dataset build completed without a materialized file pointer. "
                    f"dataset_id={dataset_id} reason={reason}"
                )

            result["dataset_file"] = dataset_file
            result["is_materialized"] = True
            result["materialization_error"] = None
            return json.dumps(result, default=str)
        except Exception as exc:
            logger.error("Error building dataset from feedback window: %s", exc, exc_info=True)
            return f"Error: {str(exc)}"
        finally:
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(
                    "Captured unexpected stdout during plexus_dataset_build_from_feedback_window: %s",
                    captured_output,
                )
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_dataset_check_associated(
        scorecard: str,
        score: str,
        score_version_id: Optional[str] = None,
        days: Optional[int] = None,
    ) -> str:
        """
        Check whether a score has an existing associated dataset and return its metadata.

        Use this to determine if a deterministic regression dataset already exists
        before creating a new one.

        Parameters:
        - scorecard: Scorecard identifier (id/key/name/external id)
        - score: Score identifier (id/key/name/external id)
        - score_version_id: Optional specific score version to match against the dataset target.
        - days: Optional lookback window used when matching optimizer feedback targets.

        Returns:
        - JSON payload with has_dataset, dataset_id, dataset_name, created_at,
          and row_count (if available from build context).
        """
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        try:
            try:
                from plexus.cli.dataset.datasets import create_client
                from plexus.cli.evaluation.evaluations import list_associated_datasets_for_score
                from plexus.cli.evaluation.evaluations import validate_dataset_materialization
                from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier
                from plexus.cli.shared.optimizer_shadow_invalidation import (
                    resolve_score_version_shadow_invalidation_metadata,
                )
            except ImportError as exc:
                return f"Error: Could not import required modules: {exc}"

            client = create_client()

            # Resolve scorecard and score to IDs
            scorecard_id = resolve_scorecard_identifier(client, scorecard)
            if not scorecard_id:
                return f"Error: Could not resolve scorecard '{scorecard}'"
            score_id = resolve_score_identifier(client, scorecard_id, score)
            if not score_id:
                return f"Error: Could not resolve score '{score}' in scorecard '{scorecard}'"

            expected_feedback_target_hash = None
            if score_version_id is not None or days is not None:
                target_metadata = resolve_score_version_shadow_invalidation_metadata(
                    client,
                    score_id=score_id,
                    score_version_id=score_version_id,
                    days=days,
                )
                expected_feedback_target_hash = target_metadata.get("feedback_target_hash")

            datasets = list_associated_datasets_for_score(client, score_id)
            if not datasets:
                return json.dumps({
                    "has_dataset": False,
                    "dataset_id": None,
                    "dataset_name": None,
                    "created_at": None,
                    "row_count": None,
                    "is_materialized": False,
                    "dataset_file": None,
                    "materialization_error": None,
                    "feedback_target_hash": expected_feedback_target_hash,
                })

            dataset = None
            row_count = None
            stored_feedback_target_hash = None
            for candidate in datasets:
                candidate_row_count = None
                candidate_feedback_target_hash = None
                if candidate.get("dataSourceVersionId"):
                    try:
                        dsv_result = client.execute(
                            """
                            query GetDataSourceVersion($id: ID!) {
                                getDataSourceVersion(id: $id) {
                                    id
                                    yamlConfiguration
                                }
                            }
                            """,
                            {"id": candidate["dataSourceVersionId"]}
                        )
                        dsv = dsv_result.get("getDataSourceVersion")
                        if dsv and dsv.get("yamlConfiguration"):
                            import yaml

                            config = yaml.safe_load(dsv["yamlConfiguration"])
                            if isinstance(config, dict):
                                stats = config.get("dataset_stats", {})
                                candidate_row_count = stats.get("row_count")
                                candidate_feedback_target_hash = stats.get("feedback_target_hash")
                    except Exception as e:
                        logger.warning("Could not read dataset build metadata from DataSourceVersion: %s", e)

                if expected_feedback_target_hash and candidate_feedback_target_hash != expected_feedback_target_hash:
                    continue

                dataset = candidate
                row_count = candidate_row_count
                stored_feedback_target_hash = candidate_feedback_target_hash
                break

            if not dataset:
                return json.dumps({
                    "has_dataset": False,
                    "dataset_id": None,
                    "dataset_name": None,
                    "created_at": None,
                    "row_count": None,
                    "is_materialized": False,
                    "dataset_file": None,
                    "materialization_error": None,
                    "feedback_target_hash": expected_feedback_target_hash,
                })

            readiness = validate_dataset_materialization(dataset)
            return json.dumps({
                "has_dataset": True,
                "dataset_id": dataset.get("id"),
                "dataset_name": dataset.get("name"),
                "created_at": dataset.get("createdAt"),
                "row_count": row_count,
                "is_materialized": bool(readiness.get("is_materialized")),
                "dataset_file": readiness.get("dataset_file"),
                "materialization_error": readiness.get("materialization_error"),
                "feedback_target_hash": stored_feedback_target_hash or expected_feedback_target_hash,
            }, default=str)
        except Exception as exc:
            logger.error("Error checking associated dataset: %s", exc, exc_info=True)
            return f"Error: {str(exc)}"
        finally:
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(
                    "Captured unexpected stdout during plexus_dataset_check_associated: %s",
                    captured_output,
                )
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_dataset_associated_from_feedback(
        scorecard: str,
        score: str,
        feedback_item_ids: List[str],
        source_report_block_id: Optional[str] = None,
        eligibility_rule: str = "unanimous non-contradiction",
    ) -> str:
        """
        Build an associated dataset directly from explicit vetted feedback IDs.

        Parameters:
        - scorecard: Scorecard identifier (id/key/name/external id)
        - score: Score identifier (id/key/name/external id)
        - feedback_item_ids: Explicit feedback item IDs to include (labels come from finalAnswerValue)
        - source_report_block_id: Optional report block ID for provenance
        - eligibility_rule: Eligibility rule string recorded in provenance/build context

        Returns:
        - JSON payload with dataset_id, row_count, and provenance summary
        """
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        try:
            try:
                from plexus.cli.dataset.datasets import create_client, build_associated_dataset_from_feedback_ids
            except ImportError as exc:
                return f"Error: Could not import dataset builder: {exc}"

            if not isinstance(feedback_item_ids, list) or not feedback_item_ids:
                return "Error: feedback_item_ids must be a non-empty list of feedback item IDs."

            client = create_client()
            result = build_associated_dataset_from_feedback_ids(
                client=client,
                scorecard_identifier=scorecard,
                score_identifier=score,
                feedback_item_ids=feedback_item_ids,
                source_report_block_id=source_report_block_id,
                eligibility_rule=eligibility_rule,
                task_id=None,
            )
            return json.dumps(result)
        except Exception as exc:
            logger.error("Error creating associated dataset from feedback IDs: %s", exc, exc_info=True)
            return f"Error: {str(exc)}"
        finally:
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(
                    "Captured unexpected stdout during plexus_dataset_associated_from_feedback: %s",
                    captured_output,
                )
            sys.stdout = old_stdout
