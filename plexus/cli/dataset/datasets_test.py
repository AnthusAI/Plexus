import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from click.testing import CliRunner
import os
from types import SimpleNamespace
import pandas as pd

from plexus.cli.dataset.datasets import dataset, build_reference_dataset_from_feedback_ids
from plexus.dashboard.api.models.data_source import DataSource

@pytest.fixture
def runner():
    return CliRunner()


def test_dataset_group_does_not_expose_reference_from_feedback_command(runner):
    result = runner.invoke(dataset, ["--help"])
    assert result.exit_code == 0
    assert "reference-from-feedback" not in result.output

@patch('plexus.cli.dataset.datasets.resolve_data_source')  # Patch in the right module  
def test_load_command_success(mock_resolve, runner):
    """Test the happy path of the load command."""
    
    # Arrange - set up environment variables for the client
    with patch.dict('os.environ', {
        'PLEXUS_API_URL': 'https://test-api.example.com',
        'PLEXUS_API_KEY': 'test-key-123'
    }):
        # Create a mock DataSource
        mock_data_source = DataSource(
            id='ds-123',
            name='Test Source',
            key='test-source',
            yamlConfiguration="""
            data:
                class: plexus.data.dummy.DummyDataCache
                parameters:
                    rows: 10
            """,
            owner='account-123'
        )
        
        # Add the attributes that are needed but not in constructor
        mock_data_source.accountId = 'account-123'
        mock_data_source.currentVersionId = 'version-123'
        mock_data_source.scoreId = 'score-123'
        mock_data_source.scorecardId = 'scorecard-123'
        
        mock_resolve.return_value = mock_data_source
        
        # Mock all the external dependencies
        with patch('plexus.cli.dataset.datasets.PlexusDashboardClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            # Mock the GraphQL responses - execute is synchronous, not async
            mock_client.execute = MagicMock(side_effect=[
                # Mock response for score query
                {'getScore': {'id': 'score-123', 'name': 'Test Score', 'championVersionId': 'score-version-123'}},
                # Mock response for createDataSet
                {'createDataSet': {'id': 'new-ds-456', 'name': 'New Dataset', 'dataSourceVersionId': 'version-123', 'scoreVersionId': 'score-version-123'}},
                # Mock response for updateDataSet
                {'updateDataSet': {'id': 'new-ds-456', 'file': 'datasets/account-123/ds-123/new-ds-456/test.parquet'}}
            ])
            
            # Mock data loading
            with patch('importlib.import_module') as mock_import:
                mock_dummy_cache_module = MagicMock()
                mock_dummy_cache_class = MagicMock()
                mock_dummy_cache_instance = MagicMock()
                
                from pandas import DataFrame
                mock_dummy_cache_instance.load_dataframe.return_value = DataFrame({'col1': [1, 2], 'col2': [3, 4]})
                
                mock_dummy_cache_class.return_value = mock_dummy_cache_instance
                mock_dummy_cache_module.DummyDataCache = mock_dummy_cache_class
                mock_import.return_value = mock_dummy_cache_module
                
                # Mock S3 upload
                with patch('plexus.cli.dataset.datasets.get_amplify_bucket') as mock_get_bucket:
                    mock_get_bucket.return_value = 'test-bucket'
                    with patch('boto3.client') as mock_boto3:
                        mock_s3_client = MagicMock()
                        mock_boto3.return_value = mock_s3_client

                        # Act
                        result = runner.invoke(dataset, ['load', '--source', 'test-source'])
        
        # Assert - just check that the command completed successfully
        assert result.exit_code == 0
        # Verify that resolve_data_source was called
        mock_resolve.assert_called_once()


@patch('plexus.cli.dataset.datasets.resolve_data_source')
def test_load_command_builtin_reference_cache_class_resolution(mock_resolve, runner):
    """Ensure built-in reference cache class resolves from plexus.data namespace."""
    with patch.dict('os.environ', {
        'PLEXUS_API_URL': 'https://test-api.example.com',
        'PLEXUS_API_KEY': 'test-key-123'
    }):
        mock_data_source = DataSource(
            id='ds-123',
            name='Test Source',
            key='test-source',
            yamlConfiguration="""
            class: ScorecardExampleReferenceItems
            scorecard: CMG EDU
            score: Identify Objections
            """,
            owner='account-123'
        )
        mock_data_source.accountId = 'account-123'
        mock_data_source.currentVersionId = 'version-123'
        mock_data_source.scoreId = 'score-123'
        mock_data_source.scorecardId = 'scorecard-123'
        mock_resolve.return_value = mock_data_source

        with patch('plexus.cli.dataset.datasets.PlexusDashboardClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.execute = MagicMock(side_effect=[
                {'getScore': {'id': 'score-123', 'name': 'Test Score', 'championVersionId': 'score-version-123'}},
                {'createDataSet': {'id': 'new-ds-456', 'name': 'New Dataset', 'dataSourceVersionId': 'version-123', 'scoreVersionId': 'score-version-123'}},
                {'updateDataSet': {'id': 'new-ds-456', 'file': 'datasets/account-123/ds-123/new-ds-456/test.parquet'}},
            ])

            with patch('importlib.import_module') as mock_import:
                mock_module = MagicMock()
                mock_class = MagicMock()
                mock_instance = MagicMock()
                from pandas import DataFrame
                mock_instance.load_dataframe.return_value = DataFrame({'col1': [1], 'col2': [2]})
                mock_class.return_value = mock_instance
                mock_module.ScorecardExampleReferenceItems = mock_class
                mock_import.return_value = mock_module

                with patch('plexus.cli.dataset.datasets.get_amplify_bucket') as mock_get_bucket:
                    mock_get_bucket.return_value = 'test-bucket'
                    with patch('boto3.client') as mock_boto3:
                        mock_boto3.return_value = MagicMock()
                        result = runner.invoke(dataset, ['load', '--source', 'test-source'])

    assert result.exit_code == 0
    mock_import.assert_called_with('plexus.data')

@patch('plexus.cli.dataset.datasets.resolve_data_source')
def test_load_command_applies_item_pipeline_to_text(mock_resolve, runner):
    """Ensure item_config drives initial text generation during dataset load."""
    import plexus.cli.dataset.datasets as datasets_module
    with patch.dict('os.environ', {
        'PLEXUS_API_URL': 'https://test-api.example.com',
        'PLEXUS_API_KEY': 'test-key-123'
    }):
        mock_data_source = DataSource(
            id='ds-123',
            name='Test Source',
            key='test-source',
            yamlConfiguration="""
            class: plexus.data.dummy.DummyDataCache
            parameters:
                rows: 10
            item:
                class: DeepgramInputSource
            """,
            owner='account-123'
        )
        mock_data_source.accountId = 'account-123'
        mock_data_source.currentVersionId = 'version-123'
        mock_data_source.scoreId = 'score-123'
        mock_data_source.scorecardId = 'scorecard-123'

        mock_resolve.return_value = mock_data_source

        with patch('plexus.cli.dataset.datasets.PlexusDashboardClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.execute = MagicMock(side_effect=[
                {'getScore': {'id': 'score-123', 'name': 'Test Score', 'championVersionId': 'score-version-123'}},
                {'createDataSet': {'id': 'new-ds-456', 'name': 'New Dataset', 'dataSourceVersionId': 'version-123', 'scoreVersionId': 'score-version-123'}},
                {'updateDataSet': {'id': 'new-ds-456', 'file': 'datasets/account-123/ds-123/new-ds-456/test.parquet'}}
            ])

            with patch('importlib.import_module') as mock_import:
                mock_dummy_cache_module = MagicMock()
                mock_dummy_cache_class = MagicMock()
                mock_dummy_cache_instance = MagicMock()

                from pandas import DataFrame
                df = DataFrame({
                    'text': ['WRONG'],
                    'item_id': ['item-123'],
                })
                mock_dummy_cache_instance.load_dataframe.return_value = df

                mock_dummy_cache_class.return_value = mock_dummy_cache_instance
                mock_dummy_cache_module.DummyDataCache = mock_dummy_cache_class
                mock_import.return_value = mock_dummy_cache_module

                with patch('plexus.cli.dataset.datasets.get_amplify_bucket') as mock_get_bucket:
                    mock_get_bucket.return_value = 'test-bucket'
                    with patch('boto3.client') as mock_boto3:
                        mock_s3_client = MagicMock()
                        mock_boto3.return_value = mock_s3_client
                        mock_item = MagicMock()
                        mock_item.to_score_input.return_value = MagicMock(text='RIGHT', metadata={})
                        mock_item.__bool__.return_value = True
                        item_stub = MagicMock()
                        item_stub.get_by_id.return_value = mock_item
                        with patch.object(datasets_module, 'Item', item_stub):
                            captured = {}

                            def capture_write_table(table, *args, **kwargs):
                                captured['df'] = table.to_pandas()
                                return None

                            with patch.object(datasets_module.pq, 'write_table', side_effect=capture_write_table):
                                result = runner.invoke(dataset, ['load', '--source', 'test-source'])

        assert result.exit_code == 0
        assert captured['df']['text'].iloc[0] == 'RIGHT'

@patch('plexus.cli.dataset.datasets.create_client')
@patch('plexus.cli.dataset.datasets.resolve_data_source')  # Patch in the right module
def test_load_command_source_not_found(mock_resolve, mock_create_client, runner):
    """Test when the data source cannot be resolved."""
    
    # Arrange
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client
    mock_resolve.return_value = None
    
    # Act
    result = runner.invoke(dataset, ['load', '--source', 'non-existent'])
    
    # Assert
    assert result.exit_code == 0 # The command exits gracefully
    mock_resolve.assert_called_once_with(mock_client, 'non-existent')
    
@pytest.mark.asyncio
@patch('plexus.cli.dataset.datasets.create_client')
async def test_resolve_data_source_by_id(mock_create_client):
    """Test the resolver function's ability to find a DataSource by ID."""
    from plexus.cli.shared.identifier_resolution import resolve_data_source
    
    # Arrange
    mock_client = AsyncMock()
    mock_create_client.return_value = mock_client
    
    mock_data_source = DataSource(id='ds-123', name='Test Source')
    
    with patch.object(DataSource, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_data_source
        
        # Act
        result = await resolve_data_source(mock_client, 'ds-123')
        
        # Assert
        mock_get.assert_called_once_with(mock_client, 'ds-123')
        assert result is not None
        assert result.id == 'ds-123'
        
@pytest.mark.asyncio
@patch('plexus.cli.dataset.datasets.create_client')
async def test_resolve_data_source_by_key(mock_create_client):
    """Test the resolver function's ability to find a DataSource by key."""
    from plexus.cli.shared.identifier_resolution import resolve_data_source
    
    # Arrange
    mock_client = AsyncMock()
    mock_create_client.return_value = mock_client
    
    mock_data_source = DataSource(id='ds-123', name='Test Source', key='test-key')
    
    with patch.object(DataSource, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None # It will fail the ID lookup
        with patch.object(DataSource, 'list_by_key', new_callable=AsyncMock) as mock_list_by_key:
            mock_list_by_key.return_value = [mock_data_source]
            
            # Act
            result = await resolve_data_source(mock_client, 'test-key')
            
            # Assert
            mock_list_by_key.assert_called_once_with(mock_client, 'test-key')
            assert result is not None
            assert result.key == 'test-key'
            
@pytest.mark.asyncio
@patch('plexus.cli.dataset.datasets.create_client')
async def test_resolve_data_source_by_name(mock_create_client):
    """Test the resolver function's ability to find a DataSource by name."""
    from plexus.cli.shared.identifier_resolution import resolve_data_source
    
    # Arrange
    mock_client = AsyncMock()
    mock_create_client.return_value = mock_client
    
    mock_data_source = DataSource(id='ds-123', name='Test Source', key='test-key')
    
    with patch.object(DataSource, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None # It will fail the ID lookup
        with patch.object(DataSource, 'list_by_key', new_callable=AsyncMock) as mock_list_by_key:
            mock_list_by_key.return_value = [] # It will fail the key lookup
            with patch.object(DataSource, 'list_by_name', new_callable=AsyncMock) as mock_list_by_name:
                mock_list_by_name.return_value = [mock_data_source]
                
                # Act
                result = await resolve_data_source(mock_client, 'Test Source')
                
                # Assert
                mock_list_by_name.assert_called_once_with(mock_client, 'Test Source')
                assert result is not None
                assert result.name == 'Test Source' 


@patch('plexus.cli.dataset.datasets._upload_dataset_parquet')
@patch('plexus.cli.dataset.datasets._create_associated_dataset_datasource_version')
@patch('plexus.cli.dataset.datasets.resolve_score_identifier')
@patch('plexus.cli.dataset.datasets.resolve_scorecard_identifier')
@patch('plexus.cli.dataset.datasets._fetch_feedback_item_with_item')
@patch('plexus.cli.dataset.datasets.FeedbackItems')
def test_build_reference_dataset_from_feedback_ids_success(
    mock_feedback_items_class,
    mock_fetch_feedback_item,
    mock_resolve_scorecard,
    mock_resolve_score,
    mock_create_datasource_version,
    mock_upload_dataset_parquet,
):
    mock_resolve_scorecard.return_value = 'scorecard-1'
    mock_resolve_score.return_value = 'score-1'
    mock_create_datasource_version.return_value = ('datasource-1', 'datasource-version-1')
    mock_upload_dataset_parquet.return_value = 'datasets/account-1/dataset-1/dataset.parquet'

    feedback_item_a = SimpleNamespace(
        id='fi-2',
        accountId='account-1',
        scorecardId='scorecard-1',
        scoreId='score-1',
        itemId='item-2',
        finalAnswerValue='Yes',
    )
    feedback_item_b = SimpleNamespace(
        id='fi-1',
        accountId='account-1',
        scorecardId='scorecard-1',
        scoreId='score-1',
        itemId='item-1',
        finalAnswerValue='No',
    )
    mock_fetch_feedback_item.side_effect = [feedback_item_a, feedback_item_b]

    built_df = pd.DataFrame(
        {
            'feedback_item_id': ['fi-1', 'fi-2'],
            'text': ['t1', 't2'],
            'metadata': ['{}', '{}'],
            'IDs': ['[]', '[]'],
            'Test Score': ['No', 'Yes'],
            'Test Score comment': ['', ''],
            'Test Score edit comment': ['', ''],
        }
    )
    row_builder = MagicMock()
    row_builder._create_dataset_rows.return_value = built_df
    mock_feedback_items_class.return_value = row_builder

    mock_client = MagicMock()
    mock_client.execute = MagicMock(side_effect=[
        {'getScore': {'id': 'score-1', 'name': 'Test Score'}},
        {'getScore': {'id': 'score-1', 'championVersionId': 'version-1'}},
        {'createDataSet': {'id': 'dataset-1'}},
        {'updateDataSet': {'id': 'dataset-1', 'file': 'datasets/account-1/dataset-1/dataset.parquet'}},
    ])

    result = build_reference_dataset_from_feedback_ids(
        client=mock_client,
        scorecard_identifier='CMG EDU',
        score_identifier='Branding and Matching',
        feedback_item_ids=['fi-2', 'fi-1', 'fi-2'],
        source_report_block_id='block-123',
        eligibility_rule='unanimous non-contradiction',
    )

    assert result['dataset_id'] == 'dataset-1'
    assert result['row_count'] == 2
    assert result['feedback_item_count'] == 2

    create_dataset_call = mock_client.execute.call_args_list[2]
    dataset_input = create_dataset_call.args[1]['input']
    assert dataset_input['scoreId'] == 'score-1'
    assert dataset_input['dataSourceVersionId'] == 'datasource-version-1'


@patch('plexus.cli.dataset.datasets.resolve_score_identifier')
@patch('plexus.cli.dataset.datasets.resolve_scorecard_identifier')
@patch('plexus.cli.dataset.datasets._fetch_feedback_item_with_item')
def test_build_reference_dataset_from_feedback_ids_rejects_mismatched_score(
    mock_fetch_feedback_item,
    mock_resolve_scorecard,
    mock_resolve_score,
):
    mock_resolve_scorecard.return_value = 'scorecard-1'
    mock_resolve_score.return_value = 'score-1'
    mock_fetch_feedback_item.return_value = SimpleNamespace(
        id='fi-1',
        accountId='account-1',
        scorecardId='scorecard-1',
        scoreId='different-score',
        itemId='item-1',
        finalAnswerValue='Yes',
    )

    mock_client = MagicMock()
    mock_client.execute = MagicMock(side_effect=[
        {'getScorecard': {'id': 'scorecard-1', 'name': 'Test Scorecard'}},
        {'getScore': {'id': 'score-1', 'name': 'Test Score'}},
    ])

    with pytest.raises(ValueError, match='do not match the requested scorecard/score'):
        build_reference_dataset_from_feedback_ids(
            client=mock_client,
            scorecard_identifier='CMG EDU',
            score_identifier='Branding and Matching',
            feedback_item_ids=['fi-1'],
        )
