import os
import boto3
from botocore.config import Config
import json
import pandas as pd
import concurrent.futures
from pydantic import Field
from plexus.CustomLogging import logging
from plexus.cli.console import console
from rich.progress import Progress
from .DataCache import DataCache
from concurrent.futures import ThreadPoolExecutor, as_completed

# boto3.set_stream_logger('', logging.WARNING)

class AWSDataLakeCache(DataCache):
    """
    A class to handle caching and retrieval of data from AWS Athena and S3.
    """
    
    class Parameters(DataCache.Parameters):
        local_cache_directory: str = Field(default="./.plexus_training_data_cache/")

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.local_cache_directory = self.parameters.local_cache_directory
        self.athena_database =       os.environ['PLEXUS_TRAINING_DATA_LAKE_DATABASE_NAME']
        self.athena_results_bucket = os.environ['PLEXUS_TRAINING_DATA_LAKE_ATHENA_RESULTS_BUCKET_NAME']
        self.s3_bucket =             os.environ['PLEXUS_TRAINING_DATA_LAKE_BUCKET_NAME']
        self.aws_region =            os.environ['AWS_REGION_NAME']
        self.athena_client =         boto3.client('athena', region_name=self.aws_region)
        config = Config(
            retries = {'max_attempts': 10, 'mode': 'adaptive'},
            max_pool_connections = 25
        )
        self.s3_client =             boto3.client('s3', region_name=self.aws_region, config=config)

        os.makedirs(self.local_cache_directory, exist_ok=True)
        logging.info("Initialized AWSDataLakeCache with local cache directory at {}".format(self.local_cache_directory))

    def execute_athena_query(self, query):
        query_execution_response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.athena_database},
            ResultConfiguration={
                'OutputLocation': f's3://{self.athena_results_bucket}/',
                'EncryptionConfiguration': {'EncryptionOption': 'SSE_S3'}
            }
        )
        logging.info("Started Athena query, received QueryExecutionId: {}".format(query_execution_response['QueryExecutionId']))
        logging.info("Query: {}".format(query))
        return query_execution_response['QueryExecutionId']

    def split_into_batches(self, form_ids, batch_size=2000):
        for i in range(0, len(form_ids), batch_size):
            yield form_ids[i:i + batch_size]

    def execute_batch_athena_queries(self, metadata_item, values):
        all_query_results = []
        total_batches = len(list(self.split_into_batches(values)))
        for batch_index, values_batch in enumerate(self.split_into_batches(values), start=1):
            batch_size = len(values_batch)
            logging.info(f"Processing batch {batch_index} of {total_batches} with {batch_size} items.")
            
            # Check if the values are integers or strings
            if isinstance(values_batch[0], int):
                values_list = ', '.join(str(value) for value in values_batch)
            else:
                values_list = ', '.join(f"'{value}'" for value in values_batch)
            
            query = f"""
                SELECT report_id, scorecard_id
                FROM "{self.athena_database}"
                WHERE "{metadata_item}" IN ({values_list})
            """
            
            logging.info(f"Executing query for batch {batch_index} of {total_batches}...")
            query_execution_id = self.execute_athena_query(query)
            query_results = self.get_query_results(query_execution_id)
            all_query_results.extend(query_results[1:])  # Skip header row
        return all_query_results

    def get_query_results(self, query_execution_id):
        import time
        
        query_execution_response = self.athena_client.get_query_execution(QueryExecutionId=query_execution_id)
        query_execution_state = query_execution_response['QueryExecution']['Status']['State']

        with console.status(f"Query in state '{query_execution_state}', waiting for completion...", spinner_style="boxBounce2"):
            while query_execution_state in ['QUEUED', 'RUNNING']:
                time.sleep(1)
                query_execution_response = self.athena_client.get_query_execution(QueryExecutionId=query_execution_id)
                query_execution_state = query_execution_response['QueryExecution']['Status']['State']

        if query_execution_state == 'SUCCEEDED':
            query_results_paginator = self.athena_client.get_paginator('get_query_results')
            query_results_iterator = query_results_paginator.paginate(QueryExecutionId=query_execution_id)
            
            all_query_results = []
            for query_results_page in query_results_iterator:
                all_query_results.extend(query_results_page['ResultSet']['Rows'])
            
            logging.info("Query succeeded and all results retrieved")
            number_of_rows = len(all_query_results)
            number_of_columns = len(all_query_results[0]['Data']) if all_query_results else 0
            logging.info(f"Query results summary: {number_of_rows} rows and {number_of_columns} columns")
            if all_query_results:
                logging.info("First few rows of query results: {}".format(all_query_results[:3]))
            return all_query_results
        elif query_execution_state in ['FAILED', 'CANCELLED']:
            error_message = query_execution_response['QueryExecution']['Status']['StateChangeReason']
            logging.error(f"Query failed with state: {query_execution_state}. Error: {error_message}")
            raise Exception(f"Query failed with state: {query_execution_state}. Error: {error_message}")

    def download_content_item(self, scorecard_id, content_id):
        prefix = f"scorecard_id={scorecard_id}/report_id={content_id}/"
        
        s3_objects = self.s3_client.list_objects_v2(Bucket=self.s3_bucket, Prefix=prefix)
        
        content_data = {}
        
        for obj in s3_objects.get('Contents', []):
            key = obj['Key']
            file_name = os.path.basename(key)
            local_path = os.path.join(self.local_cache_directory, 'content_items', key)
            
            if os.path.exists(local_path):
                logging.debug(f"{file_name} already exists locally at {local_path}")
                with open(local_path, 'r') as file:
                    content_data[file_name] = file.read()
            else:
                logging.debug(f"Downloading {file_name} from S3 bucket {self.s3_bucket}")
                s3_obj = self.s3_client.get_object(Bucket=self.s3_bucket, Key=key)
                file_content = s3_obj['Body'].read().decode('utf-8')
                
                if file_content.strip() == "":
                    logging.warning(f"Downloaded {file_name} is empty.")
                
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'w') as file:
                    file.write(file_content)
                
                content_data[file_name] = file_content

        return content_data

    def process_content_item(self, scorecard_id, content_id):
        try:
            content_data = self.download_content_item(scorecard_id, content_id)
            content_row = {'content_id': content_id, 'scorecard_id': scorecard_id}

            if not content_data:
                logging.warning(f"No content data found for content_id={content_id}, scorecard_id={scorecard_id}")
                return None

            if 'metadata.json' in content_data:
                metadata = json.loads(content_data['metadata.json'])

                content_row['form_id'] = metadata.get('form_id')
                content_row['Good Call'] = 'Yes' if metadata.get('good_call') else 'No'

                for score in metadata.get('scores', []):
                    score_name = score['name']
                    content_row[score_name] = score['answer']
                    if 'comment' in score:
                        content_row[f"{score_name} comment"] = score['comment']

                if 'school' in metadata and isinstance(metadata['school'], list):
                    for index, school_info in enumerate(metadata['school']):
                        if isinstance(school_info, dict):
                            for key, value in school_info.items():
                                content_row[f"school_{index}_{key}"] = value

            if 'transcript.txt' in content_data:
                text_content = content_data['transcript.txt']
                if text_content.strip() == "":
                    logging.warning(f"Empty text file for content_id={content_id}, scorecard_id={scorecard_id}")
                    return None
                content_row['text'] = text_content
            else:
                logging.warning(f"No text file found for content_id={content_id}, scorecard_id={scorecard_id}")
                return None
            
            return content_row
        except Exception as e:
            logging.error(f"Error processing content_id={content_id}, scorecard_id={scorecard_id}: {str(e)}")
            return None

    def load_dataframe(self, *, data, fresh=False):
        dataframes = []
        
        searches = data.get('searches')
        queries = data.get('queries')
        item_list_filename = searches[0].get('item_list_filename', None) if searches else None
        column_name = searches[0].get('column_name', None) if searches else None
        metadata_item = searches[0].get('metadata_item', None) if searches else None

        def load_values_from_file(item_list_filename, column_name):
            if item_list_filename.endswith('.csv'):
                df = pd.read_csv(item_list_filename)
            elif item_list_filename.endswith('.xlsx'):
                df = pd.read_excel(item_list_filename)
            else:
                raise ValueError("Unsupported file format. Only CSV and Excel files are supported.")
            
            if column_name not in df.columns:
                raise ValueError(f"Column '{column_name}' not found in the file.")
            
            return df[column_name].dropna().unique().tolist()

        if item_list_filename and column_name:
            values = load_values_from_file(item_list_filename, column_name)
        else:
            values = None

        # Create a unique filename for the cached dataframe based on queries or item list filename
        if values:
            identifier = os.path.basename(item_list_filename).replace('.', '_')
        else:
            filename_components = []
            for query_param in queries:
                scorecard_id = query_param['scorecard-id']
                score_id = query_param.get('score-id', 'all')
                value = query_param.get('value', 'all')
                number = query_param.get('number', 'all')
                filename_components.append(f"scorecard_id={scorecard_id}-score_id={score_id}-value={value}-number={number}")
            identifier = "_".join(filename_components)
        
        cached_dataframe_filename = f"{identifier}.h5"
        cached_dataframe_path = os.path.join(self.local_cache_directory, 'dataframes', cached_dataframe_filename)

        # Check if the cached dataframe exists
        if os.path.exists(cached_dataframe_path) and not fresh:
            logging.info("Loading cached dataframe from {}".format(cached_dataframe_path))
            dataframe = pd.read_hdf(cached_dataframe_path)
            
            # Check for NaN values in the 'text' column and log a warning
            if dataframe['text'].isna().any():
                nan_count = dataframe['text'].isna().sum()
                logging.warning(f"Loaded dataframe contains {nan_count} rows with NaN values in the 'text' column.")
            
            return dataframe

        # Build the dataframe
        all_keys = set()
        content_data = []

        def process_and_collect_keys(scorecard_id, content_id):
            content_row = self.process_content_item(scorecard_id, content_id)
            if content_row:
                all_keys.update(content_row.keys())
                return content_row
            return None

        if values:
            all_query_results = self.execute_batch_athena_queries(metadata_item, values)

            if not all_query_results:
                logging.error("No non-deprecated content items found in the database.")
                return pd.DataFrame()

            thread_count = 64

            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                future_to_row = {executor.submit(process_and_collect_keys, row['Data'][1]['VarCharValue'], row['Data'][0]['VarCharValue']): row for row in all_query_results}
                for future in concurrent.futures.as_completed(future_to_row):
                    content_row = future.result()
                    if content_row:
                        content_data.append(content_row)

            if not content_data:
                logging.error("No valid content items were processed. Unable to create dataframe.")
                return pd.DataFrame()

        else:
            
            for query_params in queries:
                scorecard_id = query_params['scorecard-id']
                main_score_id = query_params.get('score-id')
                main_value = query_params.get('value')
                calibration_answers_match = query_params.get('calibration_answers_match')
                calibration_comments_match = query_params.get('calibration_comments_match')
                minimum_calibrations = query_params.get('minimum_calibrations', 0)
                minimum_good_call_confidence = query_params.get('minimum_good_call_confidence', 0)
                minimum_confidence = query_params.get('minimum_confidence', 0)
                number = query_params.get('number')

                query = f"""
                    SELECT DISTINCT report_id
                    FROM "{self.athena_database}"
                    CROSS JOIN UNNEST(scores) AS t(score)
                    WHERE scorecard_id = '{scorecard_id}'
                """

                if main_score_id is not None:
                    query += f" AND score.id = {main_score_id}"
                
                if main_value:
                    query += f" AND score.answer = '{main_value}'"
                
                if minimum_confidence:
                    query += f" AND score.confidence >= {minimum_confidence}"
                
                if calibration_answers_match is not None:
                    query += f" AND score.calibration_answers_match = {str(calibration_answers_match).lower()}"
                
                if calibration_comments_match is not None:
                    query += f" AND score.calibration_comments_match = {str(calibration_comments_match).lower()}"
                
                query += f" AND calibrations >= {minimum_calibrations}"
                query += f" AND good_call_confidence >= {minimum_good_call_confidence}"
                
                if number:
                    query += f" LIMIT {number}"

                query_execution_id = self.execute_athena_query(query)
                query_results = self.get_query_results(query_execution_id)
                
                report_ids = [row['Data'][0]['VarCharValue'] for row in query_results[1:]]

                thread_count = 64

                with ThreadPoolExecutor(max_workers=thread_count) as executor:
                    future_to_report = {executor.submit(process_and_collect_keys, scorecard_id, report_id): report_id for report_id in report_ids}
                    for future in as_completed(future_to_report):
                        content_row = future.result()
                        if content_row:
                            content_data.append(content_row)
                            all_keys.update(content_row.keys())

        # Ensure all rows have all keys
        for row in content_data:
            for key in all_keys:
                if key not in row:
                    row[key] = None

        # Create DataFrame with all columns
        dataframe = pd.DataFrame(content_data, columns=list(all_keys))
        dataframes.append(dataframe)

        combined_dataframe = pd.concat(dataframes, ignore_index=True)
        logging.info(f"Loaded dataframe with {len(combined_dataframe)} rows and columns: {', '.join(combined_dataframe.columns)}")

        # Cache the dataframe
        dataframe_storage_directory = os.path.join(self.local_cache_directory, 'dataframes')
        os.makedirs(dataframe_storage_directory, exist_ok=True)
        dataframe_file_path = os.path.join(dataframe_storage_directory, cached_dataframe_filename)
        combined_dataframe.to_hdf(dataframe_file_path, key='df', mode='w')
        logging.info(f"Dataframe saved to {dataframe_file_path}")

        logging.info(f"Final dataframe columns: {', '.join(combined_dataframe.columns)}")
        logging.info(f"Dataframe shape: {combined_dataframe.shape}")

        return combined_dataframe