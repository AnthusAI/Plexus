import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from click.testing import CliRunner
import pandas as pd
import tempfile
from pathlib import Path
import os

from plexus.cli.analyze.analysis import analyze, feedback, topics, test_ollama, PromptAnalyzer, analyze_score_feedback


@pytest.fixture
def runner():
    """Create a Click CLI runner for testing"""
    return CliRunner()


@pytest.fixture
def mock_scorecard_registry():
    """Mock the scorecard registry"""
    with patch('plexus.cli.analyze.analysis.scorecard_registry') as mock:
        yield mock


@pytest.fixture
def mock_scorecard_class():
    """Mock scorecard class and loading"""
    with patch('plexus.cli.analyze.analysis.Scorecard') as mock:
        yield mock


@pytest.fixture
def mock_openai():
    """Mock OpenAI ChatOpenAI"""
    with patch('plexus.cli.analyze.analysis.ChatOpenAI') as mock:
        yield mock


@pytest.fixture
def mock_airtable():
    """Mock Airtable API"""
    with patch('plexus.cli.analyze.analysis.Api') as mock:
        yield mock


@pytest.fixture
def mock_pandas():
    """Mock pandas operations"""
    with patch('plexus.cli.analyze.analysis.pd') as mock:
        yield mock


@pytest.fixture
def mock_transform_functions():
    """Mock transform functions"""
    with patch('plexus.cli.analyze.analysis.transform_transcripts') as mock_transform, \
         patch('plexus.cli.analyze.analysis.transform_transcripts_llm') as mock_transform_llm, \
         patch('plexus.cli.analyze.analysis.transform_transcripts_itemize') as mock_transform_itemize, \
         patch('plexus.cli.analyze.analysis.inspect_data') as mock_inspect, \
         patch('plexus.analysis.topics.analyzer.analyze_topics') as mock_analyze:
        yield {
            'transform_transcripts': mock_transform,
            'transform_transcripts_llm': mock_transform_llm,
            'transform_transcripts_itemize': mock_transform_itemize,
            'inspect_data': mock_inspect,
            'analyze_topics': mock_analyze
        }


@pytest.fixture
def mock_ollama_test():
    """Mock the ollama test function"""
    with patch('plexus.cli.analyze.analysis.test_ollama_chat') as mock:
        yield mock


@pytest.fixture
def sample_airtable_data():
    """Sample Airtable data for testing"""
    return [
        {
            'fields': {
                'TranscriptText': 'Customer said they were happy with service',
                'Comments': 'Score should be positive',
                'QA SCORE': 8,
                'question': 'satisfaction'
            }
        },
        {
            'fields': {
                'TranscriptText': 'Customer complained about wait time',
                'Comments': 'Score should be negative',
                'QA SCORE': 3,
                'question': 'satisfaction'
            }
        }
    ]


@pytest.fixture
def mock_env_vars():
    """Mock environment variables"""
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-openai-key',
        'AIRTABLE_API_KEY': 'test-airtable-key'
    }):
        yield


class TestAnalyzeGroup:
    """Test the main analyze group command"""
    
    def test_analyze_group_exists(self, runner):
        """Test that the analyze group exists and shows help"""
        result = runner.invoke(analyze, ['--help'])
        assert result.exit_code == 0
        assert 'Analysis commands for evaluating scorecard configurations and feedback' in result.output


class TestFeedbackCommand:
    """Test the feedback subcommand"""
    
    def test_feedback_command_required_params(self, runner):
        """Test feedback command with missing required parameters"""
        result = runner.invoke(analyze, ['feedback'])
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()
    
    def test_feedback_command_scorecard_not_found(self, runner, mock_scorecard_class, mock_scorecard_registry):
        """Test feedback command when scorecard is not found"""
        mock_scorecard_registry.get.return_value = None
        
        with patch('plexus.cli.analyze.analysis.logging') as mock_logging:
            result = runner.invoke(analyze, [
                'feedback',
                '--scorecard-name', 'nonexistent',
                '--base-id', 'test-base',
                '--table-name', 'test-table'
            ])
            
            assert result.exit_code == 0
            mock_logging.error.assert_called_with("Scorecard with name 'nonexistent' not found.")
    
    def test_feedback_command_success(self, runner, mock_scorecard_class, mock_scorecard_registry, 
                                    mock_openai, mock_airtable, sample_airtable_data, mock_env_vars):
        """Test successful feedback command execution"""
        # Setup mocks
        mock_scorecard_instance = Mock()
        mock_scorecard_instance.scores = [
            {
                'name': 'satisfaction',
                'graph': [
                    {
                        'system_message': 'You are a satisfaction scorer',
                        'user_message': 'Score this transcript'
                    }
                ]
            }
        ]
        mock_scorecard_class_instance = Mock()
        mock_scorecard_class_instance.return_value = mock_scorecard_instance
        mock_scorecard_registry.get.return_value = mock_scorecard_class_instance
        
        # Mock LLM
        mock_llm = Mock()
        mock_openai.return_value = mock_llm
        
        # Mock Airtable
        mock_api = Mock()
        mock_table = Mock()
        mock_table.all.return_value = sample_airtable_data
        mock_api.table.return_value = mock_table
        mock_airtable.return_value = mock_api
        
        # Mock pandas DataFrame with proper len support
        with patch('plexus.cli.analyze.analysis.pd.DataFrame') as mock_df:
            mock_dataframe = MagicMock()
            mock_dataframe.columns = ['TranscriptText', 'Comments', 'QA SCORE']
            mock_dataframe.__len__ = Mock(return_value=2)
            mock_df.return_value = mock_dataframe
            
            with patch('plexus.cli.analyze.analysis.analyze_score_feedback') as mock_analyze_feedback:
                result = runner.invoke(analyze, [
                    'feedback',
                    '--scorecard-name', 'test-scorecard',
                    '--base-id', 'test-base',
                    '--table-name', 'test-table',
                    '--score-name', 'satisfaction'
                ])
                
                assert result.exit_code == 0
                mock_analyze_feedback.assert_called_once()
    
    def test_feedback_command_missing_columns(self, runner, mock_scorecard_class, mock_scorecard_registry,
                                            mock_openai, mock_airtable, mock_env_vars):
        """Test feedback command when required columns are missing"""
        # Setup mocks with incomplete data
        mock_scorecard_instance = Mock()
        mock_scorecard_class_instance = Mock()
        mock_scorecard_class_instance.return_value = mock_scorecard_instance
        mock_scorecard_registry.get.return_value = mock_scorecard_class_instance
        
        mock_llm = Mock()
        mock_openai.return_value = mock_llm
        
        mock_api = Mock()
        mock_table = Mock()
        mock_table.all.return_value = [{'fields': {'incomplete': 'data'}}]
        mock_api.table.return_value = mock_table
        mock_airtable.return_value = mock_api
        
        with patch('plexus.cli.analyze.analysis.pd.DataFrame') as mock_df:
            mock_dataframe = MagicMock()
            mock_dataframe.columns = ['incomplete']  # Missing required columns
            mock_df.return_value = mock_dataframe
            
            with patch('plexus.cli.analyze.analysis.logging') as mock_logging:
                result = runner.invoke(analyze, [
                    'feedback',
                    '--scorecard-name', 'test-scorecard',
                    '--base-id', 'test-base',
                    '--table-name', 'test-table'
                ])
                
                assert result.exit_code == 0
                mock_logging.error.assert_any_call(
                    "Airtable table must contain fields: ['TranscriptText', 'Comments', 'QA SCORE']"
                )
    
    def test_feedback_command_airtable_error(self, runner, mock_scorecard_class, mock_scorecard_registry,
                                           mock_openai, mock_airtable, mock_env_vars):
        """Test feedback command when Airtable API throws an error"""
        # Setup mocks
        mock_scorecard_instance = Mock()
        mock_scorecard_class_instance = Mock()
        mock_scorecard_class_instance.return_value = mock_scorecard_instance
        mock_scorecard_registry.get.return_value = mock_scorecard_class_instance
        
        mock_llm = Mock()
        mock_openai.return_value = mock_llm
        
        mock_api = Mock()
        mock_table = Mock()
        mock_table.all.side_effect = Exception("Airtable connection failed")
        mock_api.table.return_value = mock_table
        mock_airtable.return_value = mock_api
        
        with patch('plexus.cli.analyze.analysis.logging') as mock_logging:
            result = runner.invoke(analyze, [
                'feedback',
                '--scorecard-name', 'test-scorecard',
                '--base-id', 'test-base',
                '--table-name', 'test-table'
            ])
            
            assert result.exit_code == 0
            mock_logging.error.assert_any_call("Error fetching data from Airtable: Airtable connection failed")


class TestTopicsCommand:
    """Test the topics subcommand"""
    
    def test_topics_command_missing_input_file(self, runner):
        """Test topics command without required input file"""
        result = runner.invoke(analyze, ['topics'])
        assert result.exit_code != 0
        assert 'Missing option' in result.output or 'required' in result.output.lower()
    
    def test_topics_command_file_not_found(self, runner):
        """Test topics command with non-existent input file"""
        with patch('plexus.cli.analyze.analysis.logging') as mock_logging:
            result = runner.invoke(analyze, [
                'topics',
                '--input-file', 'nonexistent.parquet'
            ])
            
            assert result.exit_code == 0
            mock_logging.error.assert_called_with("Input file not found: nonexistent.parquet")
    
    def test_topics_command_inspect_mode(self, runner, mock_transform_functions, mock_pandas):
        """Test topics command in inspect mode"""
        test_file = 'test.parquet'
        
        # Mock file existence
        with patch('plexus.cli.analyze.analysis.Path') as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path.return_value = mock_path_instance
            
            # Mock pandas read_parquet
            mock_df = Mock()
            mock_pandas.read_parquet.return_value = mock_df
            
            result = runner.invoke(analyze, [
                'topics',
                '--input-file', test_file,
                '--inspect'
            ])
            
            assert result.exit_code == 0
            mock_transform_functions['inspect_data'].assert_called_once_with(mock_df, 'text')
    
    def test_topics_command_chunk_transformation(self, runner, mock_transform_functions):
        """Test topics command with chunk transformation"""
        test_file = 'test.parquet'
        
        with patch('plexus.cli.analyze.analysis.Path') as mock_path_cls:
            # Create a proper mock path instance
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_cls.return_value = mock_path_instance
            
            # Mock successful transformation
            mock_transform_functions['transform_transcripts'].return_value = (
                'input.parquet', 'output.txt', 'metadata'
            )
            
            with patch('tempfile.mkdtemp') as mock_mkdtemp, \
                 patch('plexus.cli.analyze.analysis.os.environ', {}) as mock_env:
                mock_mkdtemp.return_value = '/tmp/test_dir'
                
                result = runner.invoke(analyze, [
                    'topics',
                    '--input-file', test_file,
                    '--transform', 'chunk'
                ])
                
                assert result.exit_code == 0
                mock_transform_functions['transform_transcripts'].assert_called_once()
                mock_transform_functions['analyze_topics'].assert_called_once()
    
    def test_topics_command_llm_transformation(self, runner, mock_transform_functions):
        """Test topics command with LLM transformation"""
        test_file = 'test.parquet'
        
        with patch('plexus.cli.analyze.analysis.Path') as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_cls.return_value = mock_path_instance
            
            with patch('plexus.cli.analyze.analysis.asyncio.run') as mock_asyncio_run:
                mock_asyncio_run.return_value = ('input.parquet', 'output.txt', 'metadata')
                
                with patch('tempfile.mkdtemp') as mock_mkdtemp, \
                     patch('plexus.cli.analyze.analysis.os.environ', {}) as mock_env:
                    mock_mkdtemp.return_value = '/tmp/test_dir'
                    
                    result = runner.invoke(analyze, [
                        'topics',
                        '--input-file', test_file,
                        '--transform', 'llm',
                        '--llm-model', 'gpt-3.5-turbo',
                        '--provider', 'openai'
                    ])
                    
                    assert result.exit_code == 0
                    mock_asyncio_run.assert_called_once()
                    mock_transform_functions['analyze_topics'].assert_called_once()
    
    def test_topics_command_itemize_transformation(self, runner, mock_transform_functions):
        """Test topics command with itemize transformation"""
        test_file = 'test.parquet'
        
        with patch('plexus.cli.analyze.analysis.Path') as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_cls.return_value = mock_path_instance
            
            with patch('plexus.cli.analyze.analysis.asyncio.run') as mock_asyncio_run:
                mock_asyncio_run.return_value = ('input.parquet', 'output.txt', 'metadata')
                
                with patch('tempfile.mkdtemp') as mock_mkdtemp, \
                     patch('plexus.cli.analyze.analysis.os.environ', {}) as mock_env:
                    mock_mkdtemp.return_value = '/tmp/test_dir'
                    
                    result = runner.invoke(analyze, [
                        'topics',
                        '--input-file', test_file,
                        '--transform', 'itemize',
                        '--max-retries', '3'
                    ])
                    
                    assert result.exit_code == 0
                    mock_asyncio_run.assert_called_once()
                    mock_transform_functions['analyze_topics'].assert_called_once()
    
    def test_topics_command_skip_analysis(self, runner, mock_transform_functions):
        """Test topics command with skip analysis flag"""
        test_file = 'test.parquet'
        
        with patch('plexus.cli.analyze.analysis.Path') as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_cls.return_value = mock_path_instance
            
            mock_transform_functions['transform_transcripts'].return_value = (
                'input.parquet', 'output.txt', 'metadata'
            )
            
            result = runner.invoke(analyze, [
                'topics',
                '--input-file', test_file,
                '--skip-analysis'
            ])
            
            assert result.exit_code == 0
            mock_transform_functions['transform_transcripts'].assert_called_once()
            mock_transform_functions['analyze_topics'].assert_not_called()
    
    def test_topics_command_transformation_error(self, runner, mock_transform_functions):
        """Test topics command when transformation fails"""
        test_file = 'test.parquet'
        
        with patch('plexus.cli.analyze.analysis.Path') as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_cls.return_value = mock_path_instance
            
            # Mock transformation error
            mock_transform_functions['transform_transcripts'].side_effect = Exception("Transformation failed")
            
            with patch('plexus.cli.analyze.analysis.logging') as mock_logging:
                result = runner.invoke(analyze, [
                    'topics',
                    '--input-file', test_file
                ])
                
                assert result.exit_code == 0
                mock_logging.error.assert_any_call("Topic analysis command failed: Transformation failed")


class TestTestOllamaCommand:
    """Test the test-ollama subcommand"""
    
    def test_test_ollama_command_default_ollama(self, runner, mock_ollama_test):
        """Test test-ollama command with default Ollama provider"""
        mock_ollama_test.return_value = "The sky is blue due to Rayleigh scattering."
        
        result = runner.invoke(analyze, [
            'test-ollama',
            '--model', 'llama2',
            '--prompt', 'Why is the sky blue?'
        ])
        
        assert result.exit_code == 0
        assert 'Ollama Response' in result.output
        assert 'The sky is blue due to Rayleigh scattering.' in result.output
        mock_ollama_test.assert_called_once_with(model='llama2', prompt='Why is the sky blue?')
    
    def test_test_ollama_command_openai_provider(self, runner, mock_env_vars):
        """Test test-ollama command with OpenAI provider"""
        # Prevent actual API calls by mocking at the correct import path
        with patch('langchain_openai.ChatOpenAI') as mock_chat_openai:
            mock_llm = Mock()
            mock_response = Mock()
            mock_response.content = "OpenAI response about quantum computing"
            mock_llm.invoke.return_value = mock_response
            mock_chat_openai.return_value = mock_llm
            
            with patch('langchain.prompts.ChatPromptTemplate') as mock_template:
                mock_prompt_template = Mock()
                mock_prompt_template.format.return_value = "Formatted prompt"
                mock_template.from_template.return_value = mock_prompt_template
                
                result = runner.invoke(analyze, [
                    'test-ollama',
                    '--provider', 'openai',
                    '--model', 'gpt-3.5-turbo',
                    '--prompt', 'Explain quantum computing'
                ])
                
                assert result.exit_code == 0
                assert 'Openai Response' in result.output
                assert 'OpenAI response about quantum computing' in result.output
    
    def test_test_ollama_command_openai_missing_key(self, runner):
        """Test test-ollama command with OpenAI provider but missing API key"""
        with patch.dict(os.environ, {}, clear=True):  # Clear environment variables
            with patch('plexus.cli.analyze.analysis.logging') as mock_logging:
                result = runner.invoke(analyze, [
                    'test-ollama',
                    '--provider', 'openai',
                    '--model', 'gpt-3.5-turbo'
                ])
                
                assert result.exit_code == 0
                mock_logging.error.assert_called_with(
                    "OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass --openai-api-key"
                )
    
    def test_test_ollama_command_openai_import_error(self, runner, mock_env_vars):
        """Test test-ollama command when OpenAI package is not installed"""
        with patch('langchain_openai.ChatOpenAI', side_effect=ImportError("No module named 'langchain_openai'")):
            with patch('plexus.cli.analyze.analysis.logging') as mock_logging:
                result = runner.invoke(analyze, [
                    'test-ollama',
                    '--provider', 'openai',
                    '--model', 'gpt-3.5-turbo'
                ])
                
                assert result.exit_code == 0
                mock_logging.error.assert_called_with(
                    "OpenAI package not installed. Install with: pip install langchain-openai"
                )
    
    def test_test_ollama_command_unsupported_provider(self, runner):
        """Test test-ollama command with unsupported provider"""
        with patch('plexus.cli.analyze.analysis.logging') as mock_logging:
            result = runner.invoke(analyze, [
                'test-ollama',
                '--provider', 'unsupported'
            ])
            
            assert result.exit_code != 0  # Should fail due to Click choice validation
    
    def test_test_ollama_command_ollama_error(self, runner, mock_ollama_test):
        """Test test-ollama command when Ollama fails"""
        mock_ollama_test.side_effect = Exception("Ollama connection failed")
        
        with patch('plexus.cli.analyze.analysis.logging') as mock_logging:
            result = runner.invoke(analyze, [
                'test-ollama',
                '--provider', 'ollama'
            ])
            
            assert result.exit_code == 0
            mock_logging.error.assert_called_with("Error testing ollama: Ollama connection failed")


class TestPromptAnalyzer:
    """Test the PromptAnalyzer class"""
    
    def test_prompt_analyzer_initialization(self):
        """Test PromptAnalyzer initialization"""
        mock_llm = Mock()
        analyzer = PromptAnalyzer(mock_llm)
        
        assert analyzer.llm == mock_llm
        assert analyzer.output_parser is not None
        assert analyzer.prompt is not None
    
    def test_prompt_analyzer_analyze_feedback(self):
        """Test PromptAnalyzer analyze_feedback method"""
        mock_llm = Mock()
        mock_llm.predict.return_value = '{"common_mistakes": "test", "missing_criteria": "test", "prompt_suggestion": "test"}'
        
        analyzer = PromptAnalyzer(mock_llm)
        
        # Mock the output parser
        analyzer.output_parser = Mock()
        analyzer.output_parser.get_format_instructions.return_value = "Format instructions"
        analyzer.output_parser.parse.return_value = {
            "common_mistakes": "Inconsistent scoring",
            "missing_criteria": "Emotional tone",
            "prompt_suggestion": "Add emotion detection"
        }
        
        # Mock the prompt template
        analyzer.prompt = Mock()
        analyzer.prompt.format.return_value = "Formatted prompt"
        
        examples = [
            {"transcript": "Good service", "score": 8, "feedback": "Should be higher"},
            {"transcript": "Poor service", "score": 7, "feedback": "Should be lower"}
        ]
        
        result = analyzer.analyze_feedback("Current prompt", examples)
        
        assert result["common_mistakes"] == "Inconsistent scoring"
        assert result["missing_criteria"] == "Emotional tone"
        assert result["prompt_suggestion"] == "Add emotion detection"


class TestAnalyzeScoreFeedback:
    """Test the analyze_score_feedback function"""
    
    def test_analyze_score_feedback_function(self):
        """Test the analyze_score_feedback function"""
        # Create a proper mock DataFrame with pandas-like behavior
        mock_score_data = MagicMock(spec=pd.DataFrame)
        
        # Mock the pandas operations that the function uses
        mock_filtered_data = MagicMock()
        mock_score_data.__getitem__.return_value.notna.return_value = mock_filtered_data
        mock_score_data.__getitem__ = Mock(return_value=Mock(notna=Mock(return_value=mock_filtered_data)))
        
        # Mock the indexing operation for filtered data
        mock_filtered_data.__len__ = Mock(return_value=5)  # Return 5 records
        mock_score_data.__getitem__.return_value = mock_filtered_data
        
        mock_prompt_analyzer = Mock()
        mock_prompt_analyzer.analyze_feedback.return_value = {
            "common_mistakes": "Test mistakes",
            "missing_criteria": "Test criteria",
            "prompt_suggestion": "Test suggestion"
        }
        
        # Mock the pandas operations used in the function
        with patch('plexus.cli.analyze.analysis.logging'):
            # This should not raise an exception
            analyze_score_feedback(mock_score_data, mock_prompt_analyzer, "Test prompt")
            
            # Verify the function attempts to access the Comments column
            mock_score_data.__getitem__.assert_called()


class TestIntegration:
    """Integration tests combining multiple components"""
    
    def test_feedback_to_topics_workflow(self, runner, mock_scorecard_class, mock_scorecard_registry,
                                       mock_openai, mock_airtable, sample_airtable_data, 
                                       mock_transform_functions, mock_env_vars):
        """Test a workflow that could use both feedback and topics commands"""
        # Setup for feedback command
        mock_scorecard_instance = Mock()
        mock_scorecard_instance.scores = [
            {
                'name': 'satisfaction',
                'graph': [{'system_message': 'Test', 'user_message': 'Test'}]
            }
        ]
        mock_scorecard_class_instance = Mock()
        mock_scorecard_class_instance.return_value = mock_scorecard_instance
        mock_scorecard_registry.get.return_value = mock_scorecard_class_instance
        
        mock_llm = Mock()
        mock_openai.return_value = mock_llm
        
        mock_api = Mock()
        mock_table = Mock()
        mock_table.all.return_value = sample_airtable_data
        mock_api.table.return_value = mock_table
        mock_airtable.return_value = mock_api
        
        # Run feedback analysis
        with patch('plexus.cli.analyze.analysis.pd.DataFrame') as mock_df:
            mock_dataframe = MagicMock()
            mock_dataframe.columns = ['TranscriptText', 'Comments', 'QA SCORE']
            mock_dataframe.__len__ = Mock(return_value=2)
            mock_df.return_value = mock_dataframe
            
            with patch('plexus.cli.analyze.analysis.analyze_score_feedback'):
                feedback_result = runner.invoke(analyze, [
                    'feedback',
                    '--scorecard-name', 'test-scorecard',
                    '--base-id', 'test-base',
                    '--table-name', 'test-table',
                    '--score-name', 'satisfaction'
                ])
                
                assert feedback_result.exit_code == 0
        
        # Setup for topics command
        with patch('plexus.cli.analyze.analysis.Path') as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_cls.return_value = mock_path_instance
            
            mock_transform_functions['transform_transcripts'].return_value = (
                'input.parquet', 'output.txt', 'metadata'
            )
            
            with patch('tempfile.mkdtemp') as mock_mkdtemp, \
                 patch('plexus.cli.analyze.analysis.os.environ', {}) as mock_env:
                mock_mkdtemp.return_value = '/tmp/test_dir'
                
                topics_result = runner.invoke(analyze, [
                    'topics',
                    '--input-file', 'test.parquet'
                ])
                
                assert topics_result.exit_code == 0
                
        # Both commands should complete successfully
        assert feedback_result.exit_code == 0
        assert topics_result.exit_code == 0