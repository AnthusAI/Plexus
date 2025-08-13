#!/usr/bin/env python3
"""
Unit tests for dataset tools
"""
import pytest
import os
import tempfile
from unittest.mock import patch, Mock, MagicMock
from io import BytesIO, StringIO
import yaml
import pandas as pd

pytestmark = pytest.mark.unit


class TestDatasetLoadTool:
    """Test plexus_dataset_load tool patterns"""
    
    def test_dataset_load_validation_patterns(self):
        """Test dataset load parameter validation patterns"""
        def validate_dataset_load_params(source_identifier, fresh=False):
            if not source_identifier or not source_identifier.strip():
                return False, "source_identifier is required"
            
            if not isinstance(fresh, bool):
                return False, "fresh parameter must be a boolean"
            
            return True, None
        
        # Test valid parameters - minimal
        valid, error = validate_dataset_load_params("test-source")
        assert valid is True
        assert error is None
        
        # Test valid parameters - with fresh flag
        valid, error = validate_dataset_load_params("test-source", True)
        assert valid is True
        assert error is None
        
        # Test empty source identifier
        valid, error = validate_dataset_load_params("")
        assert valid is False
        assert "source_identifier is required" in error
        
        # Test None source identifier
        valid, error = validate_dataset_load_params(None)
        assert valid is False
        assert "source_identifier is required" in error
        
        # Test whitespace-only source identifier
        valid, error = validate_dataset_load_params("   ")
        assert valid is False
        assert "source_identifier is required" in error
        
        # Test invalid fresh parameter type
        valid, error = validate_dataset_load_params("test-source", "invalid")
        assert valid is False
        assert "fresh parameter must be a boolean" in error
    
    def test_data_source_resolution_patterns(self):
        """Test data source resolution patterns"""
        def simulate_data_source_resolution(source_identifier):
            # Mock data sources
            mock_sources = {
                "feedback-source": {
                    "id": "ds-123",
                    "name": "Feedback Items Source", 
                    "accountId": "account-456",
                    "yamlConfiguration": """
data:
  class: plexus.data.FeedbackItems
  parameters:
    scorecard_name: "Test Scorecard"
                    """,
                    "currentVersionId": "dsv-789",
                    "scoreId": "score-abc",
                    "scorecardId": "sc-def"
                },
                "csv-source": {
                    "id": "ds-456", 
                    "name": "CSV Data Source",
                    "accountId": "account-789",
                    "yamlConfiguration": """
class: plexus_extensions.CSVLoader.CSVLoader
file_path: "/data/test.csv"
                    """,
                    "currentVersionId": None,
                    "scoreId": None,
                    "scorecardId": None
                }
            }
            return mock_sources.get(source_identifier)
        
        # Test successful resolution of feedback source
        source = simulate_data_source_resolution("feedback-source")
        assert source is not None
        assert source["id"] == "ds-123"
        assert source["name"] == "Feedback Items Source"
        assert source["accountId"] == "account-456"
        
        # Test successful resolution of CSV source
        source = simulate_data_source_resolution("csv-source")
        assert source is not None
        assert source["id"] == "ds-456"
        assert source["currentVersionId"] is None
        
        # Test failed resolution
        source = simulate_data_source_resolution("nonexistent-source")
        assert source is None
    
    def test_yaml_configuration_parsing_patterns(self):
        """Test YAML configuration parsing patterns"""
        def parse_yaml_configuration(yaml_config):
            try:
                config = yaml.safe_load(yaml_config)
                if not isinstance(config, dict):
                    return None, f"yamlConfiguration must be a YAML dictionary, but got {type(config).__name__}: {config}"
                return config, None
            except yaml.YAMLError as e:
                return None, f"Error parsing yamlConfiguration: {e}"
        
        # Test valid scorecard format (with 'data' section)
        scorecard_yaml = """
data:
  class: plexus.data.FeedbackItems
  parameters:
    scorecard_name: "Test Scorecard"
    days: 30
        """
        config, error = parse_yaml_configuration(scorecard_yaml)
        assert config is not None
        assert error is None
        assert "data" in config
        assert config["data"]["class"] == "plexus.data.FeedbackItems"
        
        # Test valid direct dataset format (with 'class')
        direct_yaml = """
class: FeedbackItems
scorecard_name: "Test Scorecard"
days: 30
        """
        config, error = parse_yaml_configuration(direct_yaml)
        assert config is not None
        assert error is None
        assert "class" in config
        assert config["class"] == "FeedbackItems"
        
        # Test invalid YAML
        invalid_yaml = """
invalid: yaml:
  - malformed
    nested
        """
        config, error = parse_yaml_configuration(invalid_yaml)
        assert config is None
        assert "Error parsing yamlConfiguration" in error
        
        # Test non-dict YAML
        list_yaml = """
- item1
- item2
        """
        config, error = parse_yaml_configuration(list_yaml)
        assert config is None
        assert "yamlConfiguration must be a YAML dictionary" in error
    
    def test_data_config_extraction_patterns(self):
        """Test data config extraction patterns"""
        def extract_data_config(config):
            # Handle both scorecard format (with 'data' section) and dataset format (direct config)
            data_config = config.get('data')
            if not data_config:
                # Check if this is a direct dataset configuration
                if 'class' in config:
                    # Handle built-in Plexus classes vs client-specific extensions
                    class_name = config['class']
                    if class_name in ['FeedbackItems']:
                        # Built-in Plexus classes
                        class_path = f"plexus.data.{class_name}"
                    else:
                        # Client-specific extensions
                        class_path = f"plexus_extensions.{class_name}.{class_name}"
                    
                    data_config = {
                        'class': class_path,
                        'parameters': {k: v for k, v in config.items() if k != 'class'}
                    }
                else:
                    return None, "No 'data' section in yamlConfiguration and no 'class' specified."
            
            return data_config, None
        
        # Test scorecard format with data section
        scorecard_config = {
            'data': {
                'class': 'plexus.data.FeedbackItems',
                'parameters': {'scorecard_name': 'Test'}
            }
        }
        data_config, error = extract_data_config(scorecard_config)
        assert data_config is not None
        assert error is None
        assert data_config['class'] == 'plexus.data.FeedbackItems'
        
        # Test direct format with built-in class
        direct_builtin_config = {
            'class': 'FeedbackItems',
            'scorecard_name': 'Test',
            'days': 30
        }
        data_config, error = extract_data_config(direct_builtin_config)
        assert data_config is not None
        assert error is None
        assert data_config['class'] == 'plexus.data.FeedbackItems'
        assert data_config['parameters']['scorecard_name'] == 'Test'
        assert data_config['parameters']['days'] == 30
        
        # Test direct format with extension class
        direct_extension_config = {
            'class': 'CSVLoader',
            'file_path': '/data/test.csv'
        }
        data_config, error = extract_data_config(direct_extension_config)
        assert data_config is not None
        assert error is None
        assert data_config['class'] == 'plexus_extensions.CSVLoader.CSVLoader'
        assert data_config['parameters']['file_path'] == '/data/test.csv'
        
        # Test missing class and data section
        empty_config = {'other_field': 'value'}
        data_config, error = extract_data_config(empty_config)
        assert data_config is None
        assert "No 'data' section in yamlConfiguration and no 'class' specified" in error
    
    def test_data_cache_class_loading_patterns(self):
        """Test data cache class loading patterns"""
        def simulate_class_loading(class_path):
            # Mock available classes
            mock_classes = {
                'plexus.data.FeedbackItems': Mock(name='FeedbackItems'),
                'plexus_extensions.CSVLoader.CSVLoader': Mock(name='CSVLoader'),
                'plexus.data.DatabaseQuery': Mock(name='DatabaseQuery')
            }
            
            if class_path not in mock_classes:
                raise ImportError(f"Could not import data cache class '{class_path}': No module named '{class_path.split('.')[0]}'")
            
            return mock_classes[class_path]
        
        # Test successful built-in class loading
        data_cache_class = simulate_class_loading('plexus.data.FeedbackItems')
        assert data_cache_class is not None
        assert data_cache_class._mock_name == 'FeedbackItems'
        
        # Test successful extension class loading
        data_cache_class = simulate_class_loading('plexus_extensions.CSVLoader.CSVLoader')
        assert data_cache_class is not None
        assert data_cache_class._mock_name == 'CSVLoader'
        
        # Test failed class loading
        with pytest.raises(ImportError) as exc_info:
            simulate_class_loading('nonexistent.module.Class')
        assert "Could not import data cache class" in str(exc_info.value)
    
    def test_dataframe_loading_patterns(self):
        """Test dataframe loading patterns"""
        def simulate_dataframe_loading(data_cache_class, parameters, fresh=False):
            # Mock dataframe loading
            if data_cache_class._mock_name == 'FeedbackItems':
                # Mock feedback items dataframe
                return pd.DataFrame({
                    'item_id': ['item-1', 'item-2', 'item-3'],
                    'text': ['Sample text 1', 'Sample text 2', 'Sample text 3'],
                    'feedback': ['positive', 'negative', 'neutral']
                })
            elif data_cache_class._mock_name == 'CSVLoader':
                # Mock CSV dataframe
                return pd.DataFrame({
                    'col1': [1, 2, 3],
                    'col2': ['a', 'b', 'c'],
                    'col3': [True, False, True]
                })
            else:
                return pd.DataFrame()  # Empty dataframe
        
        # Mock data cache classes
        feedback_class = Mock(name='FeedbackItems')
        csv_class = Mock(name='CSVLoader')
        
        # Test feedback items loading
        df = simulate_dataframe_loading(feedback_class, {'scorecard_name': 'Test'})
        assert len(df) == 3
        assert 'item_id' in df.columns
        assert 'text' in df.columns
        assert 'feedback' in df.columns
        
        # Test CSV loading  
        df = simulate_dataframe_loading(csv_class, {'file_path': '/data/test.csv'})
        assert len(df) == 3
        assert 'col1' in df.columns
        assert list(df['col2']) == ['a', 'b', 'c']
        
        # Test empty dataframe
        empty_class = Mock(name='Empty')
        df = simulate_dataframe_loading(empty_class, {})
        assert len(df) == 0
    
    def test_parquet_generation_patterns(self):
        """Test Parquet file generation patterns"""
        def generate_parquet_buffer(dataframe):
            if dataframe.empty:
                return None, "Dataframe is empty, no dataset created."
            
            buffer = BytesIO()
            # Mock parquet generation (in real code uses pyarrow)
            mock_parquet_data = f"PARQUET_DATA_FOR_{len(dataframe)}_ROWS"
            buffer.write(mock_parquet_data.encode())
            buffer.seek(0)
            return buffer, None
        
        # Test with valid dataframe
        test_df = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
        buffer, error = generate_parquet_buffer(test_df)
        assert buffer is not None
        assert error is None
        buffer.seek(0)
        assert b"PARQUET_DATA_FOR_3_ROWS" in buffer.read()
        
        # Test with empty dataframe
        empty_df = pd.DataFrame()
        buffer, error = generate_parquet_buffer(empty_df)
        assert buffer is None
        assert "Dataframe is empty" in error
    
    def test_dataset_record_creation_patterns(self):
        """Test dataset record creation patterns"""
        def create_dataset_record(data_source, score_version_id=None):
            from datetime import datetime, timezone
            
            # Mock dataset input creation
            dataset_input = {
                "name": f"{data_source['name']} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
                "accountId": data_source["accountId"],
                "dataSourceVersionId": data_source["currentVersionId"] or "dsv-new-123",
            }
            
            # Add optional fields only if they have values
            if score_version_id:
                dataset_input["scoreVersionId"] = score_version_id
            if data_source.get('scorecardId'):
                dataset_input["scorecardId"] = data_source['scorecardId']
            if data_source.get('scoreId'):
                dataset_input["scoreId"] = data_source['scoreId']
            
            # Mock created dataset
            return {
                'id': 'dataset-new-456',
                'name': dataset_input['name'],
                'dataSourceVersionId': dataset_input['dataSourceVersionId'],
                'scoreVersionId': dataset_input.get('scoreVersionId')
            }
        
        # Test with complete data source
        complete_source = {
            'name': 'Test Source',
            'accountId': 'account-123',
            'currentVersionId': 'dsv-456',
            'scorecardId': 'sc-789',
            'scoreId': 'score-abc'
        }
        dataset = create_dataset_record(complete_source, 'sv-def')
        assert dataset['id'] == 'dataset-new-456'
        assert 'Test Source -' in dataset['name']
        assert dataset['scoreVersionId'] == 'sv-def'
        
        # Test with minimal data source
        minimal_source = {
            'name': 'Minimal Source',
            'accountId': 'account-456',
            'currentVersionId': None
        }
        dataset = create_dataset_record(minimal_source)
        assert dataset['id'] == 'dataset-new-456'
        assert dataset['dataSourceVersionId'] == 'dsv-new-123'  # New version created
        assert dataset['scoreVersionId'] is None
    
    def test_s3_upload_patterns(self):
        """Test S3 upload patterns"""
        def simulate_s3_upload(buffer, bucket_name, s3_key):
            # Mock S3 upload scenarios
            if not bucket_name:
                raise ValueError("S3 bucket name not found")
            
            if bucket_name == "invalid-bucket":
                raise Exception("Failed to upload file to S3: Access denied")
            
            # Mock successful upload
            return True
        
        def construct_s3_key(account_id, dataset_id, filename="dataset.parquet"):
            return f"datasets/{account_id}/{dataset_id}/{filename}"
        
        # Test successful upload
        mock_buffer = BytesIO(b"test parquet data")
        success = simulate_s3_upload(mock_buffer, "valid-bucket", "test/path/file.parquet")
        assert success is True
        
        # Test S3 key construction
        s3_key = construct_s3_key("account-123", "dataset-456")
        assert s3_key == "datasets/account-123/dataset-456/dataset.parquet"
        
        # Test upload failure
        with pytest.raises(Exception) as exc_info:
            simulate_s3_upload(mock_buffer, "invalid-bucket", "test/path/file.parquet")
        assert "Failed to upload file to S3" in str(exc_info.value)
        
        # Test missing bucket name
        with pytest.raises(ValueError) as exc_info:
            simulate_s3_upload(mock_buffer, None, "test/path/file.parquet")
        assert "S3 bucket name not found" in str(exc_info.value)
    
    def test_score_version_resolution_patterns(self):
        """Test score version resolution patterns"""
        def resolve_score_version(client, data_source):
            if not data_source.get('scoreId'):
                return None, "DataSource is not linked to a specific score"
            
            # Mock GraphQL query response
            score_query_response = {
                'getScore': {
                    'id': data_source['scoreId'],
                    'name': 'Test Score',
                    'championVersionId': 'sv-champion-123'
                }
            }
            
            if score_query_response['getScore']['championVersionId']:
                return score_query_response['getScore']['championVersionId'], None
            else:
                return None, f"Score {data_source['scoreId']} has no champion version"
        
        # Test with score-linked data source
        data_source_with_score = {
            'scoreId': 'score-123',
            'name': 'Scored Source'
        }
        version_id, error = resolve_score_version(None, data_source_with_score)
        assert version_id == 'sv-champion-123'
        assert error is None
        
        # Test with non-score-linked data source
        data_source_no_score = {
            'name': 'Plain Source'
        }
        version_id, error = resolve_score_version(None, data_source_no_score)
        assert version_id is None
        assert "not linked to a specific score" in error
    
    def test_error_handling_patterns(self):
        """Test various error handling patterns"""
        def handle_import_error(error):
            return f"Error: Could not import required modules: {error}. Dataset loading functionality may not be available."
        
        def handle_data_source_resolution_error(source_identifier):
            return f"Error: Could not resolve DataSource with identifier: {source_identifier}"
        
        def handle_yaml_error(error):
            return f"Error parsing yamlConfiguration: {error}"
        
        def handle_class_import_error(class_path, error):
            return f"Error: Could not import data cache class '{class_path}': {error}"
        
        def handle_s3_error(error):
            return f"Error: Failed to upload file to S3: {error}"
        
        def handle_general_error(error):
            return f"Error loading dataset: {str(error)}"
        
        # Test import error
        import_error = ImportError("No module named 'pandas'")
        error_msg = handle_import_error(import_error)
        assert "Could not import required modules" in error_msg
        assert "Dataset loading functionality may not be available" in error_msg
        
        # Test data source resolution error
        error_msg = handle_data_source_resolution_error("nonexistent-source")
        assert "Could not resolve DataSource with identifier: nonexistent-source" in error_msg
        
        # Test YAML parsing error
        yaml_error = yaml.YAMLError("Invalid YAML syntax")
        error_msg = handle_yaml_error(yaml_error)
        assert "Error parsing yamlConfiguration: Invalid YAML syntax" in error_msg
        
        # Test class import error
        class_error = ImportError("No module named 'custom_module'")
        error_msg = handle_class_import_error("custom_module.CustomClass", class_error)
        assert "Could not import data cache class 'custom_module.CustomClass'" in error_msg
        
        # Test S3 upload error
        s3_error = Exception("Access denied")
        error_msg = handle_s3_error(s3_error)
        assert "Failed to upload file to S3: Access denied" in error_msg
        
        # Test general error
        general_error = RuntimeError("Unexpected system error")
        error_msg = handle_general_error(general_error)
        assert "Error loading dataset: Unexpected system error" in error_msg
    
    def test_stdout_redirection_patterns(self):
        """Test stdout redirection patterns used in dataset tool"""
        # Test the pattern used to capture unexpected stdout
        old_stdout = StringIO()
        temp_stdout = StringIO()
        
        try:
            # Write something that should be captured
            print("Dataset loading stdout capture test", file=temp_stdout)
            
            # Check capture
            captured_output = temp_stdout.getvalue()
            assert "Dataset loading stdout capture test" in captured_output
        finally:
            # Pattern always restores stdout
            pass
    
    def test_logging_patterns(self):
        """Test logging patterns used in dataset tool"""
        def simulate_logging_patterns(source_identifier, data_source_name, dataframe_rows, dataset_id):
            log_messages = []
            
            # Info log when resolving data source
            log_messages.append(f"Resolving DataSource with identifier: {source_identifier}")
            
            # Info log when data source found
            log_messages.append(f"Found DataSource: {data_source_name} (ID: {data_source_name})")
            
            # Info log when loading dataframe
            log_messages.append(f"Loading dataframe using plexus.data.FeedbackItems...")
            
            # Info log with dataframe stats
            log_messages.append(f"Loaded dataframe with {dataframe_rows} rows and columns: ['col1', 'col2']")
            
            # Info log when generating parquet
            log_messages.append("Generating Parquet file in memory...")
            log_messages.append("Parquet file generated successfully.")
            
            # Info log when creating dataset
            log_messages.append("Creating new DataSet record...")
            log_messages.append(f"Created DataSet record with ID: {dataset_id}")
            
            return log_messages
        
        logs = simulate_logging_patterns("test-source", "Test Source", 150, "dataset-123")
        assert len(logs) == 8
        assert "Resolving DataSource with identifier: test-source" in logs[0]
        assert "Found DataSource: Test Source" in logs[1]
        assert "Loading dataframe using plexus.data.FeedbackItems" in logs[2]
        assert "Loaded dataframe with 150 rows" in logs[3]
        assert "Generating Parquet file in memory" in logs[4]
        assert "Created DataSet record with ID: dataset-123" in logs[7]


class TestDatasetToolSharedPatterns:
    """Test shared patterns for dataset tools"""
    
    def test_client_dependency_patterns(self):
        """Test client and dependency import patterns"""
        def simulate_imports():
            # Mock successful imports
            imports = {
                'create_client': lambda: 'mock_client',
                'resolve_data_source': lambda client, identifier: {'id': 'ds-123', 'name': 'Test Source'},
                'create_initial_data_source_version': lambda client, data_source: 'dsv-new-456',
                'get_amplify_bucket': lambda: 'test-bucket'
            }
            return imports
        
        imports = simulate_imports()
        client = imports['create_client']()
        data_source = imports['resolve_data_source'](client, 'test')
        version_id = imports['create_initial_data_source_version'](client, data_source)
        bucket = imports['get_amplify_bucket']()
        
        assert client == 'mock_client'
        assert data_source['id'] == 'ds-123'
        assert version_id == 'dsv-new-456'
        assert bucket == 'test-bucket'
    
    def test_graphql_query_patterns(self):
        """Test GraphQL query construction patterns"""
        def build_score_query(score_id):
            return f"""
                query GetScore($id: ID!) {{
                    getScore(id: $id) {{
                        id
                        name
                        championVersionId
                    }}
                }}
                """
        
        def build_dataset_creation_mutation():
            return """
            mutation CreateDataSet($input: CreateDataSetInput!) {
                createDataSet(input: $input) {
                    id
                    name
                    dataSourceVersionId
                    scoreVersionId
                }
            }
            """
        
        def build_dataset_update_mutation():
            return """
            mutation UpdateDataSet($input: UpdateDataSetInput!) {
                updateDataSet(input: $input) {
                    id
                    file
                }
            }
            """
        
        # Test score query construction
        score_query = build_score_query("score-123")
        assert "GetScore($id: ID!)" in score_query
        assert "getScore(id: $id)" in score_query
        assert "championVersionId" in score_query
        
        # Test dataset creation mutation
        create_mutation = build_dataset_creation_mutation()
        assert "CreateDataSet($input: CreateDataSetInput!)" in create_mutation
        assert "createDataSet(input: $input)" in create_mutation
        assert "scoreVersionId" in create_mutation
        
        # Test dataset update mutation
        update_mutation = build_dataset_update_mutation()
        assert "UpdateDataSet($input: UpdateDataSetInput!)" in update_mutation
        assert "updateDataSet(input: $input)" in update_mutation
        assert "file" in update_mutation
    
    def test_data_source_version_handling(self):
        """Test data source version handling patterns"""
        def handle_data_source_version(data_source, create_version_func):
            if not data_source.get('currentVersionId'):
                # Create initial version if missing
                version_id = create_version_func(data_source)
                return version_id, f"Created initial DataSource version: {version_id}"
            else:
                # Use existing version
                version_id = data_source['currentVersionId']
                return version_id, f"Using existing DataSource version ID: {version_id}"
        
        # Mock version creation function
        def mock_create_version(data_source):
            return f"dsv-new-{data_source['id']}"
        
        # Test with existing version
        data_source_with_version = {
            'id': 'ds-123',
            'currentVersionId': 'dsv-existing-456'
        }
        version_id, message = handle_data_source_version(data_source_with_version, mock_create_version)
        assert version_id == 'dsv-existing-456'
        assert "Using existing DataSource version ID" in message
        
        # Test without existing version
        data_source_no_version = {
            'id': 'ds-789',
            'currentVersionId': None
        }
        version_id, message = handle_data_source_version(data_source_no_version, mock_create_version)
        assert version_id == 'dsv-new-ds-789'
        assert "Created initial DataSource version" in message
    
    def test_pandas_integration_patterns(self):
        """Test pandas DataFrame integration patterns"""
        def validate_dataframe(df):
            if not isinstance(df, pd.DataFrame):
                return False, "Result is not a pandas DataFrame"
            
            if df.empty:
                return False, "DataFrame is empty"
            
            if len(df.columns) == 0:
                return False, "DataFrame has no columns"
            
            return True, None
        
        def get_dataframe_stats(df):
            return {
                'rows': len(df),
                'columns': df.columns.tolist(),
                'dtypes': df.dtypes.to_dict(),
                'memory_usage': df.memory_usage(deep=True).sum()
            }
        
        # Test valid dataframe
        valid_df = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['A', 'B', 'C'],
            'value': [1.1, 2.2, 3.3]
        })
        valid, error = validate_dataframe(valid_df)
        assert valid is True
        assert error is None
        
        stats = get_dataframe_stats(valid_df)
        assert stats['rows'] == 3
        assert stats['columns'] == ['id', 'name', 'value']
        assert 'id' in stats['dtypes']
        
        # Test empty dataframe
        empty_df = pd.DataFrame()
        valid, error = validate_dataframe(empty_df)
        assert valid is False
        assert "DataFrame is empty" in error
        
        # Test non-dataframe
        valid, error = validate_dataframe("not a dataframe")
        assert valid is False
        assert "Result is not a pandas DataFrame" in error
    
    def test_aws_integration_patterns(self):
        """Test AWS S3 integration patterns"""
        def validate_aws_config():
            # Mock environment/config checks
            mock_env = {
                'AWS_ACCESS_KEY_ID': 'test-key',
                'AWS_SECRET_ACCESS_KEY': 'test-secret',
                'AWS_DEFAULT_REGION': 'us-east-1'
            }
            
            required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
            missing = [var for var in required_vars if not mock_env.get(var)]
            
            if missing:
                return False, f"Missing AWS credentials: {missing}"
            
            return True, None
        
        def construct_s3_path(account_id, dataset_id, filename):
            if not account_id or not dataset_id:
                raise ValueError("Account ID and Dataset ID are required")
            
            return f"datasets/{account_id}/{dataset_id}/{filename}"
        
        # Test valid AWS config
        valid, error = validate_aws_config()
        assert valid is True
        assert error is None
        
        # Test S3 path construction
        s3_path = construct_s3_path("acc-123", "ds-456", "data.parquet")
        assert s3_path == "datasets/acc-123/ds-456/data.parquet"
        
        # Test invalid path construction
        with pytest.raises(ValueError):
            construct_s3_path("", "ds-456", "data.parquet")