import pytest
import sys
from unittest.mock import Mock, patch
import json

# Import to ensure modules are loaded
from plexus.input_sources.TextFileInputSource import TextFileInputSource
from plexus.input_sources.DeepgramInputSource import DeepgramInputSource


class TestInputSourceFactoryIntegration:
    """Integration tests focusing on InputSourceFactory workflow"""

    def load_fixture(self, filename):
        """Helper to load test fixture files"""
        with open(f"tests/fixtures/{filename}", "r") as f:
            return json.load(f)

    @patch.object(sys.modules['plexus.input_sources.TextFileInputSource'], 'download_score_result_log_file')
    def test_factory_creates_and_extracts_text_file(self, mock_download):
        """Test complete workflow: factory -> create -> extract for TextFileInputSource"""
        from plexus.input_sources.TextFileInputSource import TextFileInputSource
        from plexus.input_sources.InputSourceFactory import InputSourceFactory

        # Setup
        mock_download.return_value = ("Content from text file", None)

        # Simulate YAML config
        input_source_config = {
            "class": "TextFileInputSource",
            "options": {
                "pattern": r".*transcript\.txt$"
            }
        }

        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/path/transcript.txt"]

        # Execute: Create via factory and extract
        source_class = input_source_config.get('class')
        source_options = input_source_config.get('options', {})
        input_source = InputSourceFactory.create_input_source(source_class, **source_options)
        text = input_source.extract(item)

        # Assert
        assert text.text == "Content from text file"
        mock_download.assert_called_once_with("s3://bucket/path/transcript.txt")

    @patch.object(sys.modules['plexus.input_sources.DeepgramInputSource'], 'download_score_result_trace_file')
    def test_factory_creates_and_extracts_deepgram(self, mock_download):
        """Test complete workflow: factory -> create -> extract for DeepgramInputSource"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        from plexus.input_sources.InputSourceFactory import InputSourceFactory

        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        # Simulate YAML config
        input_source_config = {
            "class": "DeepgramInputSource",
            "options": {
                "pattern": r".*deepgram.*\.json$",
                "format": "paragraphs",
                "include_timestamps": False
            }
        }

        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/path/deepgram_transcript.json"]

        # Execute: Create via factory and extract
        source_class = input_source_config.get('class')
        source_options = input_source_config.get('options', {})
        input_source = InputSourceFactory.create_input_source(source_class, **source_options)
        text = input_source.extract(item)

        # Assert
        assert "Hello, thank you for calling customer support" in text.text
        assert "\n\n" in text.text  # Paragraphs format
        mock_download.assert_called_once_with("s3://bucket/path/deepgram_transcript.json")

    def test_factory_creates_source_without_item(self):
        """Test that factory can create sources even without an item (for testing/validation)"""
        from plexus.input_sources.TextFileInputSource import TextFileInputSource
        from plexus.input_sources.InputSourceFactory import InputSourceFactory

        # Execute
        source = InputSourceFactory.create_input_source(
            "TextFileInputSource",
            pattern=r".*\.txt$"
        )

        # Assert
        assert source is not None
        assert source.pattern.pattern == r".*\.txt$"

    @patch.object(sys.modules['plexus.input_sources.DeepgramInputSource'], 'download_score_result_trace_file')
    def test_factory_handles_different_deepgram_formats(self, mock_download):
        """Test that factory can create DeepgramInputSource with different format options"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        from plexus.input_sources.InputSourceFactory import InputSourceFactory

        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Test different format configurations
        formats = ["paragraphs", "utterances", "words", "raw"]

        for format_type in formats:
            config = {
                "class": "DeepgramInputSource",
                "options": {
                    "pattern": r".*\.json$",
                    "format": format_type
                }
            }

            source = InputSourceFactory.create_input_source(
                config["class"],
                **config["options"]
            )
            result = source.extract(item)

            # All formats should return a non-empty ScoreInput with text
            assert hasattr(result, 'text')
            assert len(result.text) > 0

    def test_factory_error_handling_for_unknown_source(self):
        """Test that factory raises clear error for unknown input source class"""
        from plexus.input_sources.TextFileInputSource import TextFileInputSource
        from plexus.input_sources.InputSourceFactory import InputSourceFactory

        with pytest.raises(ValueError, match="Unknown input source"):
            InputSourceFactory.create_input_source("NonExistentInputSource")

    @patch.object(sys.modules['plexus.input_sources.TextFileInputSource'], 'download_score_result_log_file')
    def test_factory_error_propagates_from_extract(self, mock_download):
        """Test that errors from extract() method propagate correctly"""
        from plexus.input_sources.TextFileInputSource import TextFileInputSource
        from plexus.input_sources.InputSourceFactory import InputSourceFactory

        # Setup: download fails
        mock_download.side_effect = Exception("S3 download failed")

        config = {
            "class": "TextFileInputSource",
            "options": {
                "pattern": r".*\.txt$"
            }
        }

        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/file.txt"]

        source = InputSourceFactory.create_input_source(
            config["class"],
            **config["options"]
        )

        # Execute & Assert: error should propagate
        with pytest.raises(Exception, match="S3 download failed"):
            source.extract(item)

    def test_factory_handles_complex_yaml_options(self):
        """Test that factory correctly passes through complex YAML options"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        from plexus.input_sources.InputSourceFactory import InputSourceFactory

        config = {
            "class": "DeepgramInputSource",
            "options": {
                "pattern": r".*\.json$",
                "format": "paragraphs",
                "include_timestamps": True,
                "speaker_labels": False,
                "custom_nested": {
                    "key": "value"
                }
            }
        }

        source = InputSourceFactory.create_input_source(
            config["class"],
            **config["options"]
        )

        # Assert options were passed through
        assert source.options["format"] == "paragraphs"
        assert source.options["include_timestamps"] is True
        assert source.options["speaker_labels"] is False
        assert source.options["custom_nested"]["key"] == "value"

    @patch.object(sys.modules['plexus.input_sources.TextFileInputSource'], 'download_score_result_log_file')
    def test_no_matching_attachment_raises_clear_error(self, mock_download):
        """Test that missing attachment raises clear error with available files listed"""
        from plexus.input_sources.TextFileInputSource import TextFileInputSource
        from plexus.input_sources.InputSourceFactory import InputSourceFactory

        config = {
            "class": "TextFileInputSource",
            "options": {
                "pattern": r".*transcript\.txt$"
            }
        }

        item = Mock()
        item.metadata = {}
        item.attachedFiles = [
            "s3://bucket/file1.json",
            "s3://bucket/file2.xml"
        ]

        source = InputSourceFactory.create_input_source(
            config["class"],
            **config["options"]
        )

        with pytest.raises(ValueError) as exc_info:
            source.extract(item)

        # Error message should be helpful
        error_msg = str(exc_info.value)
        assert "No attachment matching pattern" in error_msg
        assert "Available attachments:" in error_msg
        assert "file1.json" in error_msg or "file2.xml" in error_msg
