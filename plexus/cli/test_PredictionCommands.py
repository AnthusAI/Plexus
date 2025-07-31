import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock, ANY
from click.testing import CliRunner
import pandas as pd
import asyncio
import json
import os
from decimal import Decimal

from plexus.cli.PredictionCommands import (
    predict, predict_impl, output_excel, select_sample, predict_score,
    predict_score_impl, handle_exception, create_score_input,
    create_feedback_comparison
)
from plexus.scores.LangGraphScore import BatchProcessingPause


@pytest.fixture
def runner():
    """Create a Click CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def mock_scorecard_registry():
    """Mock the scorecard registry"""
    with patch('plexus.cli.PredictionCommands.scorecard_registry') as mock:
        yield mock


@pytest.fixture
def mock_scorecard_class():
    """Mock scorecard class and loading"""
    with patch('plexus.cli.PredictionCommands.Scorecard') as mock:
        yield mock


@pytest.fixture
def mock_score_class():
    """Mock Score class"""
    with patch('plexus.cli.PredictionCommands.Score') as mock:
        yield mock


@pytest.fixture
def mock_client():
    """Mock API client"""
    with patch('plexus.cli.client_utils.create_client') as mock_create:
        mock_client = Mock()
        mock_create.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_item():
    """Mock Item class"""
    with patch('plexus.dashboard.api.models.item.Item') as mock:
        yield mock


@pytest.fixture
def mock_env_vars():
    """Mock environment variables"""
    with patch.dict(os.environ, {
        'PLEXUS_ACCOUNT_KEY': 'test-account',
        'PLEXUS_API_URL': 'https://test-api.example.com',
        'PLEXUS_API_KEY': 'test-key'
    }):
        yield


@pytest.fixture
def sample_scorecard_class():
    """Sample scorecard class for testing"""
    mock_scorecard = Mock()
    mock_scorecard.properties = {'key': 'test-scorecard'}
    return mock_scorecard


@pytest.fixture
def sample_item_data():
    """Sample item data for testing"""
    return {
        'id': 'item-123',
        'text': 'Sample text for testing',
        'metadata': {'test': 'data'}
    }


class TestPredictCommand:
    """Test the main predict command"""
    
    def test_predict_command_missing_scorecard_name(self, runner):
        """Test predict command without required scorecard name"""
        result = runner.invoke(predict)
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()
    
    def test_predict_command_basic_success(self, runner, mock_scorecard_registry, sample_scorecard_class):
        """Test basic predict command success"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.asyncio') as mock_asyncio, \
             patch('plexus.cli.PredictionCommands.predict_impl') as mock_predict_impl:
            
            # Mock asyncio event loop
            mock_loop = Mock()
            mock_asyncio.new_event_loop.return_value = mock_loop
            mock_asyncio.set_event_loop.return_value = None
            mock_loop.run_until_complete.return_value = None
            mock_loop.close.return_value = None
            mock_asyncio.all_tasks.return_value = []
            
            result = runner.invoke(predict, [
                '--scorecard', 'test-scorecard',
                '--score', 'test-score'
            ])
            
            assert result.exit_code == 0
            mock_loop.run_until_complete.assert_called_once()
    
    def test_predict_command_batch_processing_pause(self, runner, mock_scorecard_registry, sample_scorecard_class):
        """Test predict command with BatchProcessingPause exception"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        batch_pause = BatchProcessingPause("test-batch-123", "test-thread-456", "Test pause message")
        
        with patch('plexus.cli.PredictionCommands.asyncio') as mock_asyncio, \
             patch('plexus.cli.PredictionCommands.rich') as mock_rich:
            
            mock_loop = Mock()
            mock_asyncio.new_event_loop.return_value = mock_loop
            mock_asyncio.set_event_loop.return_value = None
            mock_loop.run_until_complete.side_effect = batch_pause
            mock_loop.close.return_value = None
            mock_asyncio.all_tasks.return_value = []
            
            result = runner.invoke(predict, [
                '--scorecard', 'test-scorecard',
                '--score', 'test-score'
            ])
            
            assert result.exit_code == 0
            mock_rich.print.assert_called()
    
    def test_predict_command_keyboard_interrupt(self, runner, mock_scorecard_registry, sample_scorecard_class):
        """Test predict command with KeyboardInterrupt"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.asyncio') as mock_asyncio, \
             patch('plexus.cli.PredictionCommands.sys') as mock_sys:
            
            mock_loop = Mock()
            mock_asyncio.new_event_loop.return_value = mock_loop
            mock_asyncio.set_event_loop.return_value = None
            mock_loop.run_until_complete.side_effect = KeyboardInterrupt()
            mock_asyncio.all_tasks.return_value = []
            
            result = runner.invoke(predict, [
                '--scorecard', 'test-scorecard',
                '--score', 'test-score'
            ])
            
            mock_sys.exit.assert_called_with(1)
    
    def test_predict_command_general_exception(self, runner, mock_scorecard_registry, sample_scorecard_class):
        """Test predict command with general exception"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.asyncio') as mock_asyncio, \
             patch('plexus.cli.PredictionCommands.sys') as mock_sys:
            
            mock_loop = Mock()
            mock_asyncio.new_event_loop.return_value = mock_loop
            mock_asyncio.set_event_loop.return_value = None
            mock_loop.run_until_complete.side_effect = Exception("Test error")
            mock_asyncio.all_tasks.return_value = []
            
            result = runner.invoke(predict, [
                '--scorecard', 'test-scorecard',
                '--score', 'test-score'
            ])
            
            mock_sys.exit.assert_called_with(1)
    
    def test_predict_command_item_items_conflict(self, runner):
        """Test that --item and --items cannot be used together"""
        result = runner.invoke(predict, [
            '--scorecard', 'test-scorecard',
            '--score', 'test-score',
            '--item', 'item-1',
            '--items', 'item-1,item-2',
            '--format', 'yaml'
        ])
        
        # The command should fail with a non-zero exit code
        assert result.exit_code != 0
        
        # Check for the error message in output first (preferred method)
        # Note: stderr is not separately captured, so we only check result.output
        output_text = result.output
        if "Cannot specify both --item and --items" in output_text:
            # Success - error message found in output
            return
        
        # Fallback: Check the exception if output capture failed
        if result.exception:
            # Check if it's a SystemExit with code 1 (which is what we expect)
            assert isinstance(result.exception, SystemExit)
            assert result.exception.code == 1
            
            # The original BadParameter exception should be in the traceback
            import traceback
            tb_str = ''.join(traceback.format_exception(type(result.exception), result.exception, result.exception.__traceback__))
            assert "Cannot specify both --item and --items" in tb_str
        else:
            # If neither output nor exception contains the error, fail the test
            pytest.fail(f"Expected error message not found. Output: {repr(output_text)}, Exception: {result.exception}")

    def test_predict_command_multiple_scores(self, runner, mock_scorecard_registry, sample_scorecard_class):
        """Test predict command with multiple score names"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.asyncio') as mock_asyncio, \
             patch('plexus.cli.PredictionCommands.predict_impl') as mock_predict_impl:
            
            mock_loop = Mock()
            mock_asyncio.new_event_loop.return_value = mock_loop
            mock_asyncio.set_event_loop.return_value = None
            mock_loop.run_until_complete.return_value = None
            mock_loop.close.return_value = None
            mock_asyncio.all_tasks.return_value = []
            
            result = runner.invoke(predict, [
                '--scorecard', 'test-scorecard',
                '--score', 'score1,score2,score3'
            ])
            
            assert result.exit_code == 0
            # Verify predict_impl was called with parsed score names
            args, kwargs = mock_predict_impl.call_args
            assert kwargs['score_names'] == ['score1', 'score2', 'score3']


class TestPredictImpl:
    """Test the predict_impl async function"""
    
    @pytest.mark.asyncio
    async def test_predict_impl_success_fixed_format(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with successful prediction in fixed format"""
        # Mock the new individual score loading pipeline
        with patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score_with_individual_loading') as mock_predict_score, \
             patch('plexus.scores.Score.Score.load') as mock_score_load, \
             patch('plexus.cli.PredictionCommands.rich') as mock_rich:
            
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            mock_score_load.return_value = Mock()
            
            # Mock prediction result
            mock_prediction = Mock()
            mock_prediction.value = 8.5
            mock_prediction.explanation = "Test explanation"
            mock_prediction.trace = "test-trace"
            mock_predict_score.return_value = (Mock(), mock_prediction, 0.05)
            
            await predict_impl(
                scorecard_identifier='test-scorecard',
                score_names=['test-score'],
                format='fixed'
            )
            
            mock_rich.print.assert_called()
    
    @pytest.mark.asyncio
    async def test_predict_impl_success_json_format(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with successful prediction in JSON format"""
        # Mock the new individual score loading pipeline
        with patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score_with_individual_loading') as mock_predict_score, \
             patch('plexus.scores.Score.Score.load') as mock_score_load, \
             patch('builtins.print') as mock_print:
            
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            mock_score_load.return_value = Mock()
            
            # Create a more explicit Mock that ensures hasattr() works correctly
            mock_prediction = Mock(spec=['value', 'explanation', 'trace'])
            mock_prediction.value = 8.5
            mock_prediction.explanation = "Test explanation"
            mock_prediction.trace = "test-trace"
            mock_predict_score.return_value = (Mock(), mock_prediction, Decimal('0.05'))
            
            await predict_impl(
                scorecard_identifier='test-scorecard',
                score_names=['test-score'],
                format='json'
            )
            
            # Verify print was called at least once
            assert mock_print.called, "Expected print() to be called for JSON output"
            # Verify JSON was printed
            call_args = mock_print.call_args[0][0]
            parsed_json = json.loads(call_args)
            assert len(parsed_json) == 1
            assert parsed_json[0]['item_id'] == 'item-123'
            assert parsed_json[0]['scores'][0]['name'] == 'test-score'
            assert parsed_json[0]['scores'][0]['value'] == 8.5

    @pytest.mark.asyncio
    async def test_predict_impl_success_yaml_format(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with successful prediction in YAML format"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score_with_individual_loading') as mock_predict_score, \
             patch('plexus.scores.Score.Score.load') as mock_score_load, \
             patch('plexus.cli.PredictionCommands.output_yaml_prediction_results') as mock_yaml_output:
            
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            mock_score_load.return_value = Mock()
            
            mock_prediction = Mock()
            mock_prediction.value = 8.5
            mock_prediction.explanation = "Test explanation"
            mock_prediction.trace = "test-trace"
            mock_predict_score.return_value = (Mock(), mock_prediction, Decimal('0.05'))
            
            await predict_impl(
                scorecard_identifier='test-scorecard',
                score_names=['test-score'],
                format='yaml',
                include_input=True,
                include_trace=True
            )
            
            mock_yaml_output.assert_called_once_with(
                results=ANY,
                score_names=['test-score'],
                scorecard_identifier='test-scorecard',
                score_identifier='test-score',
                item_identifiers=[None],
                include_input=True,
                include_trace=True
            )
    
    @pytest.mark.asyncio
    async def test_predict_impl_excel_output(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with Excel output"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score_with_individual_loading') as mock_predict_score, \
             patch('plexus.scores.Score.Score.load') as mock_score_load, \
             patch('plexus.cli.PredictionCommands.output_excel') as mock_output_excel:
            
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            mock_score_load.return_value = Mock()
            
            mock_prediction = Mock()
            mock_prediction.value = 8.5
            mock_predict_score.return_value = (Mock(), mock_prediction, 0.05)
            
            await predict_impl(
                scorecard_identifier='test-scorecard',
                score_names=['test-score'],
                excel=True
            )
            
            mock_output_excel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_predict_impl_no_results(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with no prediction results"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score_with_individual_loading') as mock_predict_score, \
             patch('plexus.scores.Score.Score.load') as mock_score_load, \
             patch('plexus.cli.PredictionCommands.rich') as mock_rich:
            
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            mock_score_load.return_value = Mock()
            mock_predict_score.return_value = (None, None, None)
            
            await predict_impl(
                scorecard_identifier='test-scorecard',
                score_names=['test-score'],
                format='fixed'
            )
            
            mock_rich.print.assert_called_with("[yellow]No prediction results to display.[/yellow]")
    
    @pytest.mark.asyncio
    async def test_predict_impl_list_predictions(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with list of predictions"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score_with_individual_loading') as mock_predict_score, \
             patch('plexus.scores.Score.Score.load') as mock_score_load, \
             patch('plexus.cli.PredictionCommands.rich'):
            
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            mock_score_load.return_value = Mock()
            
            # Mock list of predictions
            mock_prediction = Mock()
            mock_prediction.value = 8.5
            mock_prediction.explanation = "Test explanation"
            mock_predictions = [mock_prediction]
            mock_predict_score.return_value = (Mock(), mock_predictions, 0.05)
            
            await predict_impl(
                scorecard_identifier='test-scorecard',
                score_names=['test-score']
            )
            
            # Should complete without error
    
    @pytest.mark.asyncio
    async def test_predict_impl_batch_processing_pause(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with BatchProcessingPause exception"""
        # Mock the new individual score loading pipeline
        with patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score_with_individual_loading') as mock_predict_score, \
             patch('plexus.scores.Score.Score.load') as mock_score_load:
            
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            mock_score_load.return_value = Mock()
            mock_predict_score.side_effect = BatchProcessingPause("batch-123", "thread-456", "Test pause")
            
            with pytest.raises(BatchProcessingPause):
                await predict_impl(
                    scorecard_identifier='test-scorecard',
                    score_names=['test-score']
                )

    @pytest.mark.asyncio
    async def test_predict_impl_multiple_items(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with multiple items"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score_with_individual_loading') as mock_predict_score, \
             patch('plexus.scores.Score.Score.load') as mock_score_load, \
             patch('plexus.cli.PredictionCommands.output_yaml_prediction_results') as mock_yaml_output:
            
            
            # Mock different samples for each item
            mock_select_sample.side_effect = [
                (pd.DataFrame([{'text': 'test1'}]), 'item-1'),
                (pd.DataFrame([{'text': 'test2'}]), 'item-2'),
                (pd.DataFrame([{'text': 'test3'}]), 'item-3')
            ]
            
            # Mock predictions for each item
            mock_predictions = []
            for i in range(3):
                mock_prediction = Mock()
                mock_prediction.value = f"prediction-{i+1}"
                mock_prediction.explanation = f"Test explanation {i+1}"
                mock_prediction.trace = f"test-trace-{i+1}"
                mock_predictions.append((Mock(), mock_prediction, Decimal('0.05')))
            
            mock_predict_score.side_effect = mock_predictions
            
            await predict_impl(
                scorecard_identifier='test-scorecard',
                score_names=['test-score'],
                item_identifiers=['item-1', 'item-2', 'item-3'],
                format='yaml',
                include_input=True,
                include_trace=True
            )
            
            # Verify all items were processed
            assert mock_select_sample.call_count == 3
            assert mock_predict_score.call_count == 3
            
            # Verify YAML output was called with correct parameters
            mock_yaml_output.assert_called_once()
            call_args = mock_yaml_output.call_args
            assert call_args[1]['item_identifiers'] == ['item-1', 'item-2', 'item-3']
            assert len(call_args[1]['results']) == 3
            
            # Verify each result has the correct item_id
            results = call_args[1]['results']
            assert results[0]['item_id'] == 'item-1'
            assert results[1]['item_id'] == 'item-2'
            assert results[2]['item_id'] == 'item-3'


class TestOutputExcel:
    """Test the output_excel function"""
    
    def test_output_excel_success(self):
        """Test Excel output generation"""
        results = [
            {
                'item_id': 'item-123',
                'text': 'Sample text',
                'test-score_value': 8.5,
                'test-score_explanation': 'Test explanation',
                'test-score_cost': 0.05,
                'test-score_trace': 'test-trace'
            }
        ]
        score_names = ['test-score']
        scorecard_name = 'test-scorecard'
        
        with patch('plexus.cli.PredictionCommands.pd.DataFrame') as mock_df, \
             patch('plexus.cli.PredictionCommands.pd.ExcelWriter') as mock_writer, \
             patch('plexus.cli.PredictionCommands.logging'):
            
            # Mock DataFrame to be more complete but simple
            mock_dataframe = MagicMock()
            mock_dataframe.columns.tolist.return_value = list(results[0].keys())
            mock_dataframe.columns.__contains__ = Mock(side_effect=lambda x: x in list(results[0].keys()))
            mock_dataframe.columns.__iter__ = Mock(return_value=iter(list(results[0].keys())))
            mock_dataframe.__getitem__ = Mock(return_value=mock_dataframe)
            mock_df.return_value = mock_dataframe
            
            # Mock Excel writer context manager completely
            mock_writer_context = MagicMock()
            mock_writer.return_value = mock_writer_context
            mock_writer_context.__enter__.return_value = mock_writer_context
            mock_writer_context.__exit__.return_value = None
            
            # Mock the to_excel method to avoid deep worksheet mocking
            mock_dataframe.to_excel = Mock()
            
            output_excel(results, score_names, scorecard_name)
            
            # Verify basic calls were made
            mock_df.assert_called_once_with(results)
            mock_writer.assert_called_once()


class TestSelectSample:
    """Test the select_sample function"""
    
    def test_select_sample_with_item_id_direct_lookup(self, mock_client, mock_item, sample_item_data, mock_env_vars):
        """Test select_sample with specific item ID - direct lookup"""
        # Mock Item.get_by_id success
        mock_item_instance = Mock()
        mock_item_instance.id = sample_item_data['id']
        mock_item_instance.text = sample_item_data['text']
        mock_item_instance.metadata = None  # No metadata to avoid JSON serialization issues
        mock_item.get_by_id.return_value = mock_item_instance
        
        with patch('plexus.cli.reports.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch('plexus.cli.PredictionCommands.memoized_resolve_item_identifier') as mock_resolve_item:
            mock_resolve_account.return_value = 'account-123'
            mock_resolve_item.return_value = 'item-123'
            
            sample_row, used_item_id = select_sample(
                'test-scorecard', 'test-score', 'item-123', fresh=False
            )
            
            assert used_item_id == 'item-123'
            assert isinstance(sample_row, pd.DataFrame)
            mock_item.get_by_id.assert_called_with('item-123', mock_client)
    
    def test_select_sample_with_item_id_identifier_search(self, mock_client, mock_item, sample_item_data, mock_env_vars):
        """Test select_sample with identifier search fallback"""
        # Mock item instance that will be returned by Item.get_by_id for the resolved ID
        mock_item_instance = Mock()
        mock_item_instance.id = sample_item_data['id']
        mock_item_instance.text = sample_item_data['text']
        mock_item_instance.metadata = None  # No metadata to avoid JSON serialization issues
        
        # Mock Item.get_by_id to succeed for the resolved ID
        mock_item.get_by_id.return_value = mock_item_instance
        
        with patch('plexus.cli.reports.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch('plexus.cli.PredictionCommands.memoized_resolve_item_identifier') as mock_resolve_identifier:
            
            mock_resolve_account.return_value = 'account-123'
            # Mock identifier resolution to succeed and return the item ID
            mock_resolve_identifier.return_value = 'item-123'
            
            sample_row, used_item_id = select_sample(
                'test-scorecard', 'test-score', 'search-term', fresh=False
            )
            
            assert used_item_id == 'item-123'
            assert isinstance(sample_row, pd.DataFrame)
            mock_resolve_identifier.assert_called_once_with(mock_client, 'search-term', 'account-123')
    
    def test_select_sample_item_not_found(self, mock_client, mock_item, mock_env_vars):
        """Test select_sample when item is not found"""
        sample_scorecard_class = Mock()
        sample_scorecard_class.properties = {'key': 'test-scorecard'}
        
        with patch('plexus.cli.reports.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch('plexus.cli.PredictionCommands.memoized_resolve_item_identifier') as mock_resolve_identifier:
            
            mock_resolve_account.return_value = 'account-123'
            # Mock identifier resolution to fail (return None)
            mock_resolve_identifier.return_value = None
            
            # ✅ FIXED: Expect the error from identifier resolution failing
            with pytest.raises(ValueError, match="No item found matching identifier: nonexistent"):
                select_sample(sample_scorecard_class, 'test-score', 'nonexistent', fresh=False)
    
    def test_select_sample_without_item_id(self, mock_client, mock_item, sample_item_data, mock_env_vars):
        """Test select_sample without specific item ID - gets most recent"""
        # Mock Item.list to return a proper item instance
        mock_item_instance = Mock()
        mock_item_instance.id = sample_item_data['id']
        mock_item_instance.text = sample_item_data['text']
        mock_item_instance.metadata = None  # Simple case without metadata
        mock_item.list.return_value = [mock_item_instance]
        
        with patch('plexus.cli.reports.utils.resolve_account_id_for_command') as mock_resolve_account:
            mock_resolve_account.return_value = 'account-123'
            
            sample_row, used_item_id = select_sample(
                'test-scorecard', 'test-score', None, fresh=False
            )
            
            assert used_item_id == 'item-123'
            assert isinstance(sample_row, pd.DataFrame)
            mock_item.list.assert_called_once()
    
    def test_select_sample_no_items_in_account(self, mock_client, mock_item, mock_env_vars):
        """Test select_sample when no items exist in account"""
        sample_scorecard_class = Mock()
        sample_scorecard_class.properties = {'key': 'test-scorecard'}
        
        # Mock Item.list to return empty list
        mock_item.list.return_value = []
        
        with patch('plexus.cli.reports.utils.resolve_account_id_for_command') as mock_resolve_account:
            mock_resolve_account.return_value = 'account-123'
            
            with pytest.raises(ValueError, match="No items found in the account"):
                select_sample(sample_scorecard_class, 'test-score', None, fresh=False)


class TestPredictScore:
    """Test the predict_score async function"""
    
    @pytest.mark.asyncio
    async def test_predict_score_success(self, sample_scorecard_class):
        """Test successful score prediction"""
        sample_row = pd.DataFrame([{'text': 'test text', 'metadata': '{}'}])
        
        with patch('plexus.cli.PredictionCommands.create_score_input') as mock_create_input, \
             patch('plexus.cli.PredictionCommands.predict_score_impl') as mock_predict_impl:
            
            mock_create_input.return_value = Mock()
            mock_score_instance = Mock()
            mock_prediction = Mock()
            mock_costs = 0.05
            mock_predict_impl.return_value = (mock_score_instance, mock_prediction, mock_costs)
            
            result = await predict_score(
                'test-score', sample_scorecard_class, sample_row, 'item-123'
            )
            
            assert result == (mock_score_instance, mock_prediction, mock_costs)
            mock_create_input.assert_called_once()
            mock_predict_impl.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_predict_score_batch_processing_pause(self, sample_scorecard_class):
        """Test predict_score with BatchProcessingPause"""
        sample_row = pd.DataFrame([{'text': 'test text', 'metadata': '{}'}])
        
        with patch('plexus.cli.PredictionCommands.create_score_input') as mock_create_input, \
             patch('plexus.cli.PredictionCommands.predict_score_impl') as mock_predict_impl:
            
            mock_create_input.return_value = Mock()
            mock_predict_impl.side_effect = BatchProcessingPause("batch-123", "thread-456", "Test pause")
            
            with pytest.raises(BatchProcessingPause):
                await predict_score('test-score', sample_scorecard_class, sample_row, 'item-123')
    
    @pytest.mark.asyncio
    async def test_predict_score_general_error(self, sample_scorecard_class):
        """Test predict_score with general error"""
        sample_row = pd.DataFrame([{'text': 'test text', 'metadata': '{}'}])
        
        with patch('plexus.cli.PredictionCommands.create_score_input') as mock_create_input, \
             patch('plexus.cli.PredictionCommands.predict_score_impl') as mock_predict_impl:
            
            mock_create_input.return_value = Mock()
            mock_predict_impl.side_effect = Exception("Test error")
            
            with pytest.raises(Exception, match="Test error"):
                await predict_score('test-score', sample_scorecard_class, sample_row, 'item-123')


class TestPredictScoreImpl:
    """Test the predict_score_impl async function"""
    
    @pytest.mark.asyncio
    async def test_predict_score_impl_success(self, mock_score_class, sample_scorecard_class):
        """Test successful score implementation"""
        mock_score_instance = AsyncMock()
        mock_score_instance.predict.return_value = Mock(value=8.5)
        mock_score_instance.get_accumulated_costs = Mock(return_value=0.05)
        mock_score_class.from_name.return_value = mock_score_instance
        
        result = await predict_score_impl(
            scorecard_class=sample_scorecard_class,
            score_name='test-score',
            item_id='item-123',
            input_data=Mock()
        )
        
        assert len(result) == 3
        assert result[0] == mock_score_instance
        assert result[2] == 0.05  # costs
        mock_score_instance.async_setup.assert_called_once()
        mock_score_instance.predict.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_predict_score_impl_no_costs(self, mock_score_class, sample_scorecard_class):
        """Test score implementation when costs are not available"""
        mock_score_instance = AsyncMock()
        mock_score_instance.predict.return_value = Mock(value=8.5)
        if hasattr(mock_score_instance, 'get_accumulated_costs'):
            del mock_score_instance.get_accumulated_costs
        mock_score_class.from_name.return_value = mock_score_instance
        
        result = await predict_score_impl(
            scorecard_class=sample_scorecard_class,
            score_name='test-score',
            item_id='item-123',
            input_data=Mock()
        )
        
        assert result[2] is None  # costs should be None
    
    @pytest.mark.asyncio
    async def test_predict_score_impl_batch_processing_pause(self, mock_score_class, sample_scorecard_class):
        """Test score implementation with BatchProcessingPause"""
        mock_score_instance = AsyncMock()
        mock_score_instance.predict.side_effect = BatchProcessingPause("batch-123", "thread-456", "Test pause")
        mock_score_class.from_name.return_value = mock_score_instance
        
        with pytest.raises(BatchProcessingPause):
            await predict_score_impl(
                scorecard_class=sample_scorecard_class,
                score_name='test-score',
                item_id='item-123',
                input_data=Mock()
            )
    
    @pytest.mark.asyncio
    async def test_predict_score_impl_error_with_cleanup(self, mock_score_class, sample_scorecard_class):
        """Test score implementation with error and cleanup"""
        mock_score_instance = AsyncMock()
        mock_score_instance.predict.side_effect = Exception("Test error")
        mock_score_class.from_name.return_value = mock_score_instance
        
        with pytest.raises(Exception, match="Test error"):
            await predict_score_impl(
                scorecard_class=sample_scorecard_class,
                score_name='test-score',
                item_id='item-123',
                input_data=Mock()
            )
        
        mock_score_instance.cleanup.assert_called_once()


class TestHandleException:
    """Test the handle_exception function"""
    
    def test_handle_exception_batch_processing_pause(self):
        """Test exception handler with BatchProcessingPause"""
        mock_loop = Mock()
        batch_pause = BatchProcessingPause("batch-123", "thread-456", "Test pause message")
        context = {
            'exception': batch_pause,
            'message': 'Test message'
        }
        
        with patch('builtins.print') as mock_print:
            handle_exception(mock_loop, context, 'test-scorecard', 'test-score')
            
            mock_loop.stop.assert_called_once()
            mock_print.assert_called()
    
    def test_handle_exception_general_exception(self):
        """Test exception handler with general exception"""
        mock_loop = Mock()
        context = {
            'exception': Exception("Test error"),
            'message': 'Test message'
        }
        
        with patch('plexus.cli.PredictionCommands.logging'):
            handle_exception(mock_loop, context)
            
            mock_loop.default_exception_handler.assert_called_once_with(context)
            mock_loop.stop.assert_called_once()




class TestCreateScoreInput:
    """Test the create_score_input function"""
    
    def test_create_score_input_with_sample_row(self, mock_score_class):
        """Test create_score_input with sample row data"""
        mock_score_input_class = Mock()
        mock_score_instance = Mock()
        mock_score_instance.Input = mock_score_input_class
        mock_score_class.from_name.return_value = mock_score_instance
        
        sample_scorecard_class = Mock()
        sample_scorecard_class.properties = {'key': 'test-scorecard'}
        
        sample_row = pd.DataFrame([{
            'text': 'test text',
            'metadata': json.dumps({'existing': 'data'})
        }])
        
        result = create_score_input(sample_row, 'item-123', sample_scorecard_class, 'test-score')
        
        mock_score_input_class.assert_called_once()
        call_args = mock_score_input_class.call_args
        assert call_args[1]['text'] == 'test text'
        assert 'item_id' in call_args[1]['metadata']
    
    def test_create_score_input_without_sample_row(self, mock_score_class):
        """Test create_score_input without sample row data"""
        mock_score_input_class = Mock()
        mock_score_instance = Mock()
        mock_score_instance.Input = mock_score_input_class
        mock_score_class.from_name.return_value = mock_score_instance
        
        sample_scorecard_class = Mock()
        sample_scorecard_class.properties = {'key': 'test-scorecard'}
        
        result = create_score_input(None, 'item-123', sample_scorecard_class, 'test-score')
        
        mock_score_input_class.assert_called_once()
        call_args = mock_score_input_class.call_args
        assert call_args[1]['text'] == ''
        assert call_args[1]['metadata']['item_id'] == 'item-123'
    
    def test_create_score_input_no_input_class(self, mock_score_class):
        """Test create_score_input when Input class is not available"""
        mock_score_instance = Mock()
        # No Input attribute
        delattr(mock_score_instance, 'Input')
        mock_score_class.from_name.return_value = mock_score_instance
        
        # Mock the default Score.Input
        mock_default_input = Mock()
        mock_score_class.Input = mock_default_input
        
        sample_scorecard_class = Mock()
        sample_scorecard_class.properties = {'key': 'test-scorecard'}
        
        sample_row = pd.DataFrame([{'text': 'test text', 'metadata': '{}'}])
        
        result = create_score_input(sample_row, 'item-123', sample_scorecard_class, 'test-score')
        
        mock_default_input.assert_called_once()


class TestIntegration:
    """Integration tests combining multiple components"""
    
    def test_predict_command_full_workflow(self, runner, mock_scorecard_registry, mock_client, mock_env_vars):
        """Test complete predict command workflow"""
        # Setup mocks for full workflow
        sample_scorecard_class = Mock()
        sample_scorecard_class.properties = {'key': 'test-scorecard'}
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.asyncio') as mock_asyncio, \
             patch('plexus.cli.PredictionCommands.predict_impl') as mock_predict_impl, \
             patch('plexus.cli.reports.utils.resolve_account_id_for_command') as mock_resolve_account:
            
            mock_loop = Mock()
            mock_asyncio.new_event_loop.return_value = mock_loop
            mock_asyncio.set_event_loop.return_value = None
            mock_loop.run_until_complete.return_value = None
            mock_loop.close.return_value = None
            mock_asyncio.all_tasks.return_value = []
            
            mock_resolve_account.return_value = 'account-123'
            
            result = runner.invoke(predict, [
                '--scorecard', 'test-scorecard',
                '--score', 'test-score',
                '--item', 'item-123',
                '--format', 'json',
                '--excel'
            ])
            
            assert result.exit_code == 0
            mock_predict_impl.assert_called_once()
            # Verify parameters were passed correctly (checking by position since it's a complex call)
            args, kwargs = mock_predict_impl.call_args
            # The coroutine was created with these args, so just verify it was called
            assert mock_predict_impl.called


class TestFeedbackComparison:
    """Test class for feedback comparison functionality."""
    
    def setup_method(self):
        """Setup for each test method."""
        self.mock_feedback_item = Mock()
        self.mock_feedback_item.finalAnswerValue = "Yes"
        self.mock_feedback_item.initialAnswerValue = "No"
        self.mock_feedback_item.editCommentValue = "Corrected after review"
        self.mock_feedback_item.editorName = "human_reviewer"
        
    def test_create_feedback_comparison_agreement(self):
        """Test create_feedback_comparison when prediction matches ground truth."""
        current_prediction = {
            'test_score_value': 'Yes',
            'test_score_explanation': 'AI determined this is positive'
        }
        
        result = create_feedback_comparison(
            current_prediction, 
            self.mock_feedback_item, 
            'test_score'
        )
        
        expected = {
            "current_prediction": {
                "value": "Yes",
                "explanation": "AI determined this is positive"
            },
            "ground_truth": "Yes",
            "isAgreement": True
        }
        
        assert result == expected
        assert result["isAgreement"] is True
    
    def test_create_feedback_comparison_disagreement(self):
        """Test create_feedback_comparison when prediction doesn't match ground truth."""
        current_prediction = {
            'test_score_value': 'No',
            'test_score_explanation': 'AI determined this is negative'
        }
        
        result = create_feedback_comparison(
            current_prediction, 
            self.mock_feedback_item, 
            'test_score'
        )
        
        expected = {
            "current_prediction": {
                "value": "No",
                "explanation": "AI determined this is negative"
            },
            "ground_truth": "Yes",
            "isAgreement": False
        }
        
        assert result == expected
        assert result["isAgreement"] is False
    
    def test_create_feedback_comparison_case_insensitive(self):
        """Test that comparison is case-insensitive."""
        current_prediction = {
            'test_score_value': 'yes',  # lowercase
            'test_score_explanation': 'AI says yes'
        }
        
        # Ground truth is "Yes" (uppercase from mock)
        result = create_feedback_comparison(
            current_prediction, 
            self.mock_feedback_item, 
            'test_score'
        )
        
        assert result["isAgreement"] is True
    
    def test_create_feedback_comparison_none_values(self):
        """Test create_feedback_comparison with None values."""
        current_prediction = {
            'test_score_value': None,
            'test_score_explanation': None
        }
        
        self.mock_feedback_item.finalAnswerValue = None
        
        result = create_feedback_comparison(
            current_prediction, 
            self.mock_feedback_item, 
            'test_score'
        )
        
        assert result["current_prediction"]["value"] is None
        assert result["ground_truth"] is None
        assert result["isAgreement"] is False  # None values should not agree
    
    def test_create_feedback_comparison_missing_explanation(self):
        """Test create_feedback_comparison when explanation is missing."""
        current_prediction = {
            'test_score_value': 'Yes'
            # No explanation field
        }
        
        result = create_feedback_comparison(
            current_prediction, 
            self.mock_feedback_item, 
            'test_score'
        )
        
        assert result["current_prediction"]["explanation"] is None
        assert result["current_prediction"]["value"] == "Yes"
        assert result["isAgreement"] is True


class TestPredictCommandWithFeedback:
    """Test class for predict command with feedback comparison integration."""
    
    @pytest.fixture
    def mock_scorecard_class(self):
        """Mock scorecard class."""
        scorecard = Mock()
        scorecard.properties = {'key': 'test_scorecard'}
        scorecard.scores = [{'name': 'test_score', 'id': 1}]
        return scorecard
    
    def test_predict_command_with_feedback_comparison_flag(self, mock_scorecard_class):
        """Test that predict command accepts and passes through compare_to_feedback flag."""
        runner = CliRunner()
        
        with patch('plexus.cli.PredictionCommands.predict_impl') as mock_predict_impl:
            # Mock the async predict_impl function
            mock_predict_impl.return_value = None
            
            result = runner.invoke(predict, [
                '--scorecard', 'test-scorecard',
                '--score', 'test-score',
                '--item', 'item-123',
                '--compare-to-feedback'  # Test the new flag
            ])
            
            # Should complete without error
            assert result.exit_code == 0
            
            # Verify predict_impl was called with compare_to_feedback=True
            mock_predict_impl.assert_called_once()
            # Get the arguments passed to predict_impl
            args, kwargs = mock_predict_impl.call_args
            # The compare_to_feedback should be passed as a keyword argument
            assert kwargs.get('compare_to_feedback') is True
    
    def test_predict_command_without_feedback_comparison_flag(self, mock_scorecard_class):
        """Test that predict command defaults compare_to_feedback to False."""
        runner = CliRunner()
        
        with patch('plexus.cli.PredictionCommands.predict_impl') as mock_predict_impl:
            mock_predict_impl.return_value = None
            
            result = runner.invoke(predict, [
                '--scorecard', 'test-scorecard',  
                '--score', 'test-score',
                '--item', 'item-123'
                # No --compare-to-feedback flag
            ])
            
            assert result.exit_code == 0
            
            # Verify predict_impl was called with compare_to_feedback=False (default)
            mock_predict_impl.assert_called_once()
            args, kwargs = mock_predict_impl.call_args
            assert kwargs.get('compare_to_feedback') is False


class TestFeedbackComparisonIntegration:
    """Test class for end-to-end feedback comparison integration."""
    
    def test_create_feedback_comparison_with_real_structure(self):
        """Test create_feedback_comparison with realistic prediction structure."""
        # Simulate a realistic prediction result structure
        current_prediction = {
            'agent_helpfulness_value': 'Helpful',
            'agent_helpfulness_explanation': 'The agent provided clear guidance and resolved the issue',
            'agent_helpfulness_confidence': 0.85
        }
        
        mock_feedback_item = Mock()
        mock_feedback_item.finalAnswerValue = 'Helpful'  # Agreement case
        mock_feedback_item.initialAnswerValue = 'Not Helpful'
        
        result = create_feedback_comparison(
            current_prediction, 
            mock_feedback_item, 
            'agent_helpfulness'
        )
        
        # Verify the structure matches expected output format
        assert 'current_prediction' in result
        assert 'ground_truth' in result
        assert 'isAgreement' in result
        
        assert result['current_prediction']['value'] == 'Helpful'
        assert result['current_prediction']['explanation'] == 'The agent provided clear guidance and resolved the issue'
        assert result['ground_truth'] == 'Helpful'
        assert result['isAgreement'] is True
    
    def test_feedback_comparison_with_numeric_values(self):
        """Test feedback comparison with numeric score values."""
        current_prediction = {
            'satisfaction_score_value': 8.5,
            'satisfaction_score_explanation': 'High satisfaction based on positive indicators'
        }
        
        mock_feedback_item = Mock()
        mock_feedback_item.finalAnswerValue = '8.5'  # String representation
        
        result = create_feedback_comparison(
            current_prediction, 
            mock_feedback_item, 
            'satisfaction_score'
        )
        
        # Should handle numeric to string comparison  
        assert result['current_prediction']['value'] == 8.5
        assert result['ground_truth'] == '8.5'
        assert result['isAgreement'] is True  # str(8.5) == str('8.5') after lowercasing
    
    def test_feedback_comparison_edge_cases(self):
        """Test edge cases in feedback comparison logic."""
        test_cases = [
            # Case 1: Empty string vs None
            ({
                'test_score_value': '',
                'test_score_explanation': 'Empty prediction'
            }, None, False),
            
            # Case 2: Whitespace differences
            ({
                'test_score_value': ' Yes ',
                'test_score_explanation': 'With whitespace'
            }, 'Yes', False),  # Current implementation doesn't strip whitespace
            
            # Case 3: Boolean-like strings  
            ({
                'test_score_value': 'true',
                'test_score_explanation': 'Boolean string'
            }, 'True', True),  # Case insensitive due to .lower()
        ]
        
        for prediction, ground_truth, expected_agreement in test_cases:
            mock_feedback_item = Mock()
            mock_feedback_item.finalAnswerValue = ground_truth
            
            result = create_feedback_comparison(
                prediction, 
                mock_feedback_item, 
                'test_score'
            )
            
            assert result['isAgreement'] is expected_agreement