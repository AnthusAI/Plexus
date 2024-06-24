import os
import re
import boto3
import json
from tqdm import tqdm
import pandas as pd
from io import StringIO
from plexus.CustomLogging import logging
from plexus.cli.console import console
from concurrent.futures import ThreadPoolExecutor
from call_criteria_database import Report
from rich.progress import Progress
from rich.console import Console
from rich.table import Table
from rich.columns import Columns
from functools import partial

class DataCache:
    def __init__(self,
        athena_database,
        athena_results_bucket,
        s3_bucket,
        local_cache_directory="./.plexus_training_data_cache/"):

        self.aws_region = os.environ['AWS_REGION_NAME']
        self.athena_client = boto3.client('athena', region_name=self.aws_region)
        self.s3_client = boto3.client('s3', region_name=self.aws_region)
        self.athena_database = athena_database
        self.athena_results_bucket = athena_results_bucket
        self.s3_bucket = s3_bucket
        self.local_cache_directory = local_cache_directory

        os.makedirs(self.local_cache_directory, exist_ok=True)
        logging.info("Initialized DataCache with local cache directory at [purple][b]{}[/b][/purple]".format(self.local_cache_directory), extra={"highlighter": None})

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

    def download_report(self, scorecard_id, report_id):
        metadata_key = f"scorecard_id={scorecard_id}/report_id={report_id}/metadata.json"
        transcript_key = f"scorecard_id={scorecard_id}/report_id={report_id}/transcript.json"
        transcript_txt_key = f"scorecard_id={scorecard_id}/report_id={report_id}/transcript.txt"

        metadata_local_path = os.path.join(self.local_cache_directory, 'reports', metadata_key)
        transcript_local_path = os.path.join(self.local_cache_directory, 'reports', transcript_key)
        transcript_txt_local_path = os.path.join(self.local_cache_directory, 'reports', transcript_txt_key)

        if os.path.exists(metadata_local_path):
            logging.debug("Metadata already exists locally at {}".format(metadata_local_path))
            with open(metadata_local_path, 'r') as metadata_file:
                metadata = json.load(metadata_file)
        else:
            logging.debug("Downloading metadata from S3 bucket {}".format(self.s3_bucket))
            metadata_obj = self.s3_client.get_object(Bucket=self.s3_bucket, Key=metadata_key)
            metadata = json.loads(metadata_obj['Body'].read().decode('utf-8'))
            os.makedirs(os.path.dirname(metadata_local_path), exist_ok=True)
            with open(metadata_local_path, 'w') as metadata_file:
                json.dump(metadata, metadata_file)

        if os.path.exists(transcript_txt_local_path):
            logging.debug("Transcript text already exists locally at {}".format(transcript_txt_local_path))
            with open(transcript_txt_local_path, 'r') as transcript_txt_file:
                transcript_txt = transcript_txt_file.read()
        else:
            logging.info("Downloading transcript text from S3 bucket {}".format(self.s3_bucket))
            transcript_txt_obj = self.s3_client.get_object(Bucket=self.s3_bucket, Key=transcript_txt_key)
            transcript_txt = transcript_txt_obj['Body'].read().decode('utf-8')
            os.makedirs(os.path.dirname(transcript_txt_local_path), exist_ok=True)
            with open(transcript_txt_local_path, 'w') as transcript_txt_file:
                transcript_txt_file.write(transcript_txt)

        # return metadata, transcript, transcript_txt
        return metadata, transcript_txt

    def load_dataframe_from_queries(self, *, queries):
        dataframes = []

        filename_components = []
        for query_param in queries:
            scorecard_id = query_param['scorecard-id']
            score_id = query_param.get('score-id', 'all')
            value = query_param.get('value', 'all')
            number = query_param.get('number', 'all')
            filename_components.append(f"scorecard_id={scorecard_id}-score_id={score_id}-value={value}-number={number}")
        cached_dataframe_filename = "_".join(filename_components) + '.h5'

        cached_dataframe_path = os.path.join(self.local_cache_directory, 'dataframes', cached_dataframe_filename)
        if os.path.exists(cached_dataframe_path):
            logging.info("Loading cached dataframe from {}".format(cached_dataframe_path))
            return pd.read_hdf(cached_dataframe_path)

        logging.info("Loading dataframe with queries: {}".format(queries))
        
        for query_params in queries:
            scorecard_id = query_params['scorecard-id']
            if 'score-id' in query_params and ('value' in query_params or 'values' in query_params):
                score_id = query_params['score-id']
                values = query_params['values'] if 'values' in query_params else [query_params['value']]
                number = query_params.get('number')
                
                values_list = ', '.join(f"'{value}'" for value in values)
                
                query = f"""
                    SELECT report_id
                    FROM (
                        SELECT report_id, MIN(CASE WHEN t.score.id = {score_id} THEN t.score.answer END) AS value
                        FROM "{self.athena_database}"
                        CROSS JOIN UNNEST(scores) AS t(score)
                        GROUP BY report_id
                    )
                    WHERE value IN ({values_list})
                """
                if number:
                    query += f" LIMIT {number}"
            elif 'scorecard-id' in query_params:
                number = query_params.get('number')
                
                query = f"""
                    SELECT DISTINCT report_id
                    FROM "{self.athena_database}"
                    WHERE scorecard_id = '{scorecard_id}'
                """
                if number:
                    query += f" LIMIT {number}"
            else:
                raise ValueError("Invalid query parameters. Each query must contain 'scorecard-id'.")
            
            query_execution_id = self.execute_athena_query(query)
            query_results = self.get_query_results(query_execution_id)
            
            report_ids = [row['Data'][0]['VarCharValue'] for row in query_results[1:]]
            
            def process_report(report_id):
                try:
                    report_metadata, report_transcript_txt = self.download_report(scorecard_id, report_id)
                    report_row = {'report_id': report_id}
                    for score in report_metadata.get('scores', []):
                        report_row[score['name']] = score['answer']
                    report_row['Transcription'] = report_transcript_txt
                    return report_row
                except self.s3_client.exceptions.NoSuchKey:
                    logging.warning(f"Report with ID {report_id} not found in S3 bucket.")
                    return None
            
            with ThreadPoolExecutor() as executor:
                with Progress() as progress:
                    task = progress.add_task("[cyan]Processing reports...", total=len(report_ids))
                    report_data_futures = [executor.submit(process_report, report_id) for report_id in report_ids]
                    report_data = []
                    for future in report_data_futures:
                        result = future.result()
                        if result is not None:
                            report_data.append(result)
                        progress.update(task, advance=1)  
    
            dataframe = pd.DataFrame(report_data)
            dataframes.append(dataframe)
        
        combined_dataframe = pd.concat(dataframes, ignore_index=True)
        
        logging.info(f"Loaded dataframe with {len(combined_dataframe)} rows and columns: {', '.join(combined_dataframe.columns)}")
        
        dataframe_storage_directory = os.path.join(self.local_cache_directory, 'dataframes')
        os.makedirs(dataframe_storage_directory, exist_ok=True)
        dataframe_file_path = os.path.join(dataframe_storage_directory, cached_dataframe_filename)
        combined_dataframe.to_hdf(dataframe_file_path, key='df', mode='w')
        logging.info(f"Dataframe saved to {dataframe_file_path}")

        return combined_dataframe
    
    def load_dataframe_from_excel(self, *, file_path, scorecard_id, score_name):
        encoded_file_path = re.sub(r'[/\s.]', '_', file_path)
        filename_components = f"file_path={encoded_file_path}-scorecard_id={scorecard_id}-score_name={score_name}"
        cached_dataframe_filename = filename_components + '.h5'

        cached_dataframe_path = os.path.join(self.local_cache_directory, 'dataframes', cached_dataframe_filename)
        if os.path.exists(cached_dataframe_path):
            logging.info(f"Loading cached dataframe from {cached_dataframe_path}")
            return pd.read_hdf(cached_dataframe_path)

        if not os.path.exists(file_path):
            logging.error(f"Excel file not found: {file_path}")
            raise FileNotFoundError(f"Excel file not found: {file_path}")

        logging.info(f"Loading dataframe from Excel file: {file_path}")
        dataframe = pd.read_excel(file_path)

        dataframe[score_name] = dataframe[score_name].map({1: "Yes", 0: "No"})
        
        # Filter out everything except for the 'Session_ID' and 'SOLD_FLAG' columns.
        dataframe = dataframe[['Session_ID', score_name]]

        unique_session_ids = dataframe['Session_ID'].unique()
        report_ids = []
                    
        # Fetch all report IDs in a single query
        session_id_to_report_id = Report.find_reports_by_session_ids(unique_session_ids)
            
        # Map session IDs to report IDs
        console.log("Mapping session IDs to report IDs...")
        report_ids = dataframe['Session_ID'].map(session_id_to_report_id)

        # Add those report IDs as a column to the dataframe
        dataframe['report_id'] = report_ids

        def process_report(report_id):
            try:
                report_metadata, report_transcript_txt = self.download_report(scorecard_id, report_id)
                report_row = {'report_id': report_id}
                for score in report_metadata.get('scores', []):
                    report_row[score['name']] = score['answer']
                report_row['Transcription'] = report_transcript_txt
                return report_row
            except self.s3_client.exceptions.NoSuchKey:
                logging.warning(f"Report with ID {report_id} not found in S3 bucket.")
                return None
        
        with ThreadPoolExecutor() as executor:
            with Progress() as progress:
                task = progress.add_task("[cyan]Processing reports...", total=len(report_ids))
                report_data_futures = [executor.submit(process_report, report_id) for report_id in report_ids]
                report_data = []
                for future in report_data_futures:
                    result = future.result()
                    if result:
                        if 'Transcription' in result:
                            dataframe.loc[dataframe['report_id'] == result['report_id'], 'Transcription'] = result['Transcription']
                        else:
                            dataframe.loc[dataframe['report_id'] == result['report_id'], 'Transcription'] = None
                    progress.update(task, advance=1)  
        
        total_rows = len(dataframe)
        rows_with_transcription = dataframe['Transcription'].notna().sum()
        rows_without_transcription = total_rows - rows_with_transcription

        console.print(f"Total rows: {total_rows}")
        console.print(f"Rows with transcription: {rows_with_transcription}")
        console.print(f"Rows without transcription: {rows_without_transcription}")

        dataframe = dataframe.dropna(subset=['Transcription'])

        updated_total_rows = len(dataframe)
        updated_rows_with_transcription = dataframe['Transcription'].notna().sum()

        console.print(f"After removal:")
        console.print(f"Total rows: {updated_total_rows}")
        console.print(f"Rows with transcription: {updated_rows_with_transcription}")

        min_count = dataframe[score_name].value_counts().min()
        balanced_dataframe = dataframe.groupby(score_name).apply(lambda x: x.sample(min_count)).reset_index(drop=True)
        dataframe = balanced_dataframe

        console.print(f"Balanced dataframe: {len(dataframe)}")

        dataframe['Transcription'] = dataframe['Transcription'].apply(lambda x: '\n'.join([line[7:] for line in x.split('\n') if line.startswith("Customer: ")]))
        dataframe = dataframe[dataframe['Transcription'].str.strip() != '']

        # os.makedirs(os.path.dirname(cached_dataframe_path), exist_ok=True)
        # dataframe.to_hdf(cached_dataframe_path, key='df', mode='w')
        # logging.info(f"Cached dataframe saved to {cached_dataframe_path}")

        return dataframe
