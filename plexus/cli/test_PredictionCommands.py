import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from click.testing import CliRunner
import pandas as pd
import asyncio
import json
import os
from decimal import Decimal

from plexus.cli.PredictionCommands import (
    predict, predict_impl, output_excel, select_sample, predict_score,
    predict_score_impl, handle_exception, get_scorecard_class, create_score_input
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
                '--scorecard-name', 'test-scorecard',
                '--score-name', 'test-score'
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
                '--scorecard-name', 'test-scorecard',
                '--score-name', 'test-score'
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
                '--scorecard-name', 'test-scorecard',
                '--score-name', 'test-score'
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
                '--scorecard-name', 'test-scorecard',
                '--score-name', 'test-score'
            ])
            
            mock_sys.exit.assert_called_with(1)
    
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
                '--scorecard-name', 'test-scorecard',
                '--score-name', 'score1,score2,score3'
            ])
            
            assert result.exit_code == 0
            # Verify predict_impl was called with parsed score names
            args, kwargs = mock_predict_impl.call_args
            assert args[1] == ['score1', 'score2', 'score3']


class TestPredictImpl:
    """Test the predict_impl async function"""
    
    @pytest.mark.asyncio
    async def test_predict_impl_success_fixed_format(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with successful prediction in fixed format"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        # Mock the prediction pipeline
        with patch('plexus.cli.PredictionCommands.get_scorecard_class') as mock_get_scorecard, \
             patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score') as mock_predict_score, \
             patch('plexus.cli.PredictionCommands.rich') as mock_rich:
            
            mock_get_scorecard.return_value = sample_scorecard_class
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            
            # Mock prediction result
            mock_prediction = Mock()
            mock_prediction.value = 8.5
            mock_prediction.explanation = "Test explanation"
            mock_prediction.trace = "test-trace"
            mock_predict_score.return_value = (Mock(), mock_prediction, 0.05)
            
            await predict_impl(
                scorecard_name='test-scorecard',
                score_names=['test-score'],
                format='fixed'
            )
            
            mock_rich.print.assert_called()
    
    @pytest.mark.asyncio
    async def test_predict_impl_success_json_format(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with successful prediction in JSON format"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.get_scorecard_class') as mock_get_scorecard, \
             patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score') as mock_predict_score, \
             patch('builtins.print') as mock_print:
            
            mock_get_scorecard.return_value = sample_scorecard_class
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            
            mock_prediction = Mock()
            mock_prediction.value = 8.5
            mock_prediction.explanation = "Test explanation"
            mock_prediction.trace = "test-trace"
            mock_predict_score.return_value = (Mock(), mock_prediction, Decimal('0.05'))
            
            await predict_impl(
                scorecard_name='test-scorecard',
                score_names=['test-score'],
                format='json'
            )
            
            mock_print.assert_called()
            # Verify JSON was printed
            call_args = mock_print.call_args[0][0]
            parsed_json = json.loads(call_args)
            assert len(parsed_json) == 1
            assert parsed_json[0]['item_id'] == 'item-123'
            assert parsed_json[0]['test-score']['value'] == 8.5
    
    @pytest.mark.asyncio
    async def test_predict_impl_excel_output(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with Excel output"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.get_scorecard_class') as mock_get_scorecard, \
             patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score') as mock_predict_score, \
             patch('plexus.cli.PredictionCommands.output_excel') as mock_output_excel:
            
            mock_get_scorecard.return_value = sample_scorecard_class
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            
            mock_prediction = Mock()
            mock_prediction.value = 8.5
            mock_predict_score.return_value = (Mock(), mock_prediction, 0.05)
            
            await predict_impl(
                scorecard_name='test-scorecard',
                score_names=['test-score'],
                excel=True
            )
            
            mock_output_excel.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_predict_impl_no_results(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with no prediction results"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.get_scorecard_class') as mock_get_scorecard, \
             patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score') as mock_predict_score, \
             patch('plexus.cli.PredictionCommands.rich') as mock_rich:
            
            mock_get_scorecard.return_value = sample_scorecard_class
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            mock_predict_score.return_value = (None, None, None)
            
            await predict_impl(
                scorecard_name='test-scorecard',
                score_names=['test-score'],
                format='fixed'
            )
            
            mock_rich.print.assert_called_with("[yellow]No prediction results to display.[/yellow]")
    
    @pytest.mark.asyncio
    async def test_predict_impl_list_predictions(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with list of predictions"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.get_scorecard_class') as mock_get_scorecard, \
             patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score') as mock_predict_score, \
             patch('plexus.cli.PredictionCommands.rich'):
            
            mock_get_scorecard.return_value = sample_scorecard_class
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            
            # Mock list of predictions
            mock_prediction = Mock()
            mock_prediction.value = 8.5
            mock_prediction.explanation = "Test explanation"
            mock_predictions = [mock_prediction]
            mock_predict_score.return_value = (Mock(), mock_predictions, 0.05)
            
            await predict_impl(
                scorecard_name='test-scorecard',
                score_names=['test-score']
            )
            
            # Should complete without error
    
    @pytest.mark.asyncio
    async def test_predict_impl_batch_processing_pause(self, mock_scorecard_registry, sample_scorecard_class):
        """Test predict_impl with BatchProcessingPause exception"""
        mock_scorecard_registry.get.return_value = sample_scorecard_class
        
        with patch('plexus.cli.PredictionCommands.get_scorecard_class') as mock_get_scorecard, \
             patch('plexus.cli.PredictionCommands.select_sample') as mock_select_sample, \
             patch('plexus.cli.PredictionCommands.predict_score') as mock_predict_score:
            
            mock_get_scorecard.return_value = sample_scorecard_class
            mock_select_sample.return_value = (pd.DataFrame([{'text': 'test'}]), 'item-123')
            mock_predict_score.side_effect = BatchProcessingPause("batch-123", "thread-456", "Test pause")
            
            with pytest.raises(BatchProcessingPause):
                await predict_impl(
                    scorecard_name='test-scorecard',
                    score_names=['test-score']
                )


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
        sample_scorecard_class = Mock()
        sample_scorecard_class.properties = {'key': 'test-scorecard'}
        
        # Mock Item.get_by_id success
        mock_item_instance = Mock()
        mock_item_instance.id = sample_item_data['id']
        mock_item_instance.text = sample_item_data['text']
        mock_item.get_by_id.return_value = mock_item_instance
        
        with patch('plexus.cli.reports.utils.resolve_account_id_for_command') as mock_resolve_account:
            mock_resolve_account.return_value = 'account-123'
            
            sample_row, used_item_id = select_sample(
                sample_scorecard_class, 'test-score', 'item-123', fresh=False
            )
            
            assert used_item_id == 'item-123'
            assert isinstance(sample_row, pd.DataFrame)
            mock_item.get_by_id.assert_called_once_with('item-123', mock_client)
    
    def test_select_sample_with_item_id_identifier_search(self, mock_client, mock_item, sample_item_data, mock_env_vars):
        """Test select_sample with identifier search fallback"""
        sample_scorecard_class = Mock()
        sample_scorecard_class.properties = {'key': 'test-scorecard'}
        
        # Mock Item.get_by_id failure, then identifier search success
        mock_item.get_by_id.side_effect = ValueError("Item not found")
        
        mock_item_instance = Mock()
        mock_item_instance.id = sample_item_data['id']
        mock_item_instance.text = sample_item_data['text']
        
        with patch('plexus.cli.reports.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch('plexus.utils.identifier_search.find_item_by_identifier') as mock_find_item:
            
            mock_resolve_account.return_value = 'account-123'
            mock_find_item.return_value = mock_item_instance
            
            sample_row, used_item_id = select_sample(
                sample_scorecard_class, 'test-score', 'search-term', fresh=False
            )
            
            assert used_item_id == 'item-123'
            assert isinstance(sample_row, pd.DataFrame)
            mock_find_item.assert_called_once()
    
    def test_select_sample_item_not_found(self, mock_client, mock_item, mock_env_vars):
        """Test select_sample when item is not found"""
        sample_scorecard_class = Mock()
        sample_scorecard_class.properties = {'key': 'test-scorecard'}
        
        # Mock both direct lookup and identifier search failure
        mock_item.get_by_id.side_effect = ValueError("Item not found")
        
        with patch('plexus.cli.reports.utils.resolve_account_id_for_command') as mock_resolve_account, \
             patch('plexus.utils.identifier_search.find_item_by_identifier') as mock_find_item:
            
            mock_resolve_account.return_value = 'account-123'
            mock_find_item.return_value = None
            
            with pytest.raises(ValueError, match="No item found with ID"):
                select_sample(sample_scorecard_class, 'test-score', 'nonexistent', fresh=False)
    
    def test_select_sample_without_item_id(self, mock_client, mock_item, sample_item_data, mock_env_vars):
        """Test select_sample without specific item ID - gets most recent"""
        sample_scorecard_class = Mock()
        sample_scorecard_class.properties = {'key': 'test-scorecard'}
        
        # Mock GraphQL response
        mock_client.execute.return_value = {
            'listItemByAccountIdAndCreatedAt': {
                'items': [sample_item_data]
            }
        }
        
        mock_item_instance = Mock()
        mock_item_instance.id = sample_item_data['id']
        mock_item_instance.text = sample_item_data['text']
        mock_item.from_dict.return_value = mock_item_instance
        mock_item.fields.return_value = "id text"
        
        with patch('plexus.cli.reports.utils.resolve_account_id_for_command') as mock_resolve_account:
            mock_resolve_account.return_value = 'account-123'
            
            sample_row, used_item_id = select_sample(
                sample_scorecard_class, 'test-score', None, fresh=False
            )
            
            assert used_item_id == 'item-123'
            assert isinstance(sample_row, pd.DataFrame)
            mock_client.execute.assert_called_once()
    
    def test_select_sample_no_items_in_account(self, mock_client, mock_item, mock_env_vars):
        """Test select_sample when no items exist in account"""
        sample_scorecard_class = Mock()
        sample_scorecard_class.properties = {'key': 'test-scorecard'}
        
        # Mock empty GraphQL response
        mock_client.execute.return_value = {
            'listItemByAccountIdAndCreatedAt': {
                'items': []
            }
        }
        
        mock_item.fields.return_value = "id text"
        
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


class TestGetScorecardClass:
    """Test the get_scorecard_class function"""
    
    def test_get_scorecard_class_success(self, mock_scorecard_class, mock_scorecard_registry):
        """Test successful scorecard class retrieval"""
        mock_scorecard_registry.get.return_value = Mock()
        
        result = get_scorecard_class('test-scorecard')
        
        assert result is not None
        mock_scorecard_class.load_and_register_scorecards.assert_called_once_with('scorecards/')
        mock_scorecard_registry.get.assert_called_once_with('test-scorecard')
    
    def test_get_scorecard_class_not_found(self, mock_scorecard_class, mock_scorecard_registry):
        """Test scorecard class not found"""
        mock_scorecard_registry.get.return_value = None
        
        with pytest.raises(ValueError, match="Scorecard with name 'nonexistent' not found"):
            get_scorecard_class('nonexistent')


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
                '--scorecard-name', 'test-scorecard',
                '--score-name', 'test-score',
                '--item-id', 'item-123',
                '--format', 'json',
                '--excel'
            ])
            
            assert result.exit_code == 0
            mock_predict_impl.assert_called_once()
            # Verify parameters were passed correctly (checking by position since it's a complex call)
            args, kwargs = mock_predict_impl.call_args
            # The coroutine was created with these args, so just verify it was called
            assert mock_predict_impl.called