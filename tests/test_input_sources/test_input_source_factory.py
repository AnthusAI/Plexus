import pytest
import sys
from unittest.mock import patch, Mock
from plexus.input_sources.InputSourceFactory import InputSourceFactory
from plexus.input_sources.InputSource import InputSource
from plexus.input_sources.TextFileInputSource import TextFileInputSource
from plexus.input_sources.DeepgramInputSource import DeepgramInputSource


class TestInputSourceFactory:
    """Test cases for InputSourceFactory"""

    def test_create_text_file_input_source(self):
        """Test creating TextFileInputSource via factory"""
        # Execute
        source = InputSourceFactory.create_input_source(
            "TextFileInputSource",
            pattern=r".*\.txt$"
        )

        # Assert
        assert isinstance(source, TextFileInputSource)
        assert isinstance(source, InputSource)
        assert source.pattern is not None
        assert source.pattern.pattern == r".*\.txt$"

    def test_create_deepgram_input_source(self):
        """Test creating DeepgramInputSource via factory"""
        # Execute
        source = InputSourceFactory.create_input_source(
            "DeepgramInputSource",
            pattern=r".*deepgram.*\.json$",
            format="paragraphs",
            include_timestamps=True
        )

        # Assert
        assert isinstance(source, DeepgramInputSource)
        assert isinstance(source, TextFileInputSource)
        assert isinstance(source, InputSource)
        assert source.pattern.pattern == r".*deepgram.*\.json$"
        assert source.options["format"] == "paragraphs"
        assert source.options["include_timestamps"] is True

    def test_create_with_no_options(self):
        """Test creating input source with no options"""
        # Execute
        source = InputSourceFactory.create_input_source("TextFileInputSource")

        # Assert
        assert isinstance(source, TextFileInputSource)
        assert source.pattern is None
        assert source.options == {}

    def test_create_with_pattern_only(self):
        """Test creating input source with pattern only"""
        # Execute
        source = InputSourceFactory.create_input_source(
            "TextFileInputSource",
            pattern=r".*\.json$"
        )

        # Assert
        assert source.pattern.pattern == r".*\.json$"
        assert source.options == {}

    def test_create_with_multiple_options(self):
        """Test creating input source with multiple options"""
        # Execute
        source = InputSourceFactory.create_input_source(
            "DeepgramInputSource",
            pattern=r".*\.json$",
            format="utterances",
            include_timestamps=False,
            speaker_labels=True,
            custom_option="value"
        )

        # Assert
        assert source.options == {
            "format": "utterances",
            "include_timestamps": False,
            "speaker_labels": True,
            "custom_option": "value"
        }

    def test_create_unknown_source_raises_error(self):
        """Test that creating unknown input source raises ValueError"""
        # Execute & Assert
        with pytest.raises(ValueError, match="Unknown input source"):
            InputSourceFactory.create_input_source(
                "NonExistentInputSource",
                pattern=r".*\.txt$"
            )

    def test_create_with_typo_in_name(self):
        """Test that typo in class name raises clear error"""
        # Execute & Assert
        with pytest.raises(ValueError, match="Unknown input source"):
            InputSourceFactory.create_input_source(
                "TextFileInputSorce",  # Typo: "Sorce" instead of "Source"
                pattern=r".*\.txt$"
            )

    def test_create_with_wrong_case(self):
        """Test that wrong case in class name raises error (case-sensitive)"""
        # Execute & Assert
        with pytest.raises(ValueError, match="Unknown input source"):
            InputSourceFactory.create_input_source(
                "textfileinputsource",  # Wrong case
                pattern=r".*\.txt$"
            )

    def test_create_with_empty_string_name(self):
        """Test that empty string source name raises error"""
        # Execute & Assert
        with pytest.raises(ValueError, match="Unknown input source"):
            InputSourceFactory.create_input_source("", pattern=r".*\.txt$")

    @patch.object(sys.modules['plexus.input_sources.InputSourceFactory'], 'importlib')
    def test_create_import_error_propagates(self, mock_importlib):
        """Test that import errors are logged and re-raised"""
        # Setup
        mock_importlib.import_module.side_effect = ImportError("Module not found")

        # Execute & Assert
        with pytest.raises(ImportError, match="Module not found"):
            InputSourceFactory.create_input_source("TextFileInputSource")

    def test_create_preserves_pattern_regex(self):
        """Test that regex patterns are correctly compiled"""
        # Execute
        source = InputSourceFactory.create_input_source(
            "TextFileInputSource",
            pattern=r"^deepgram_\d{4}\.json$"
        )

        # Assert
        assert source.pattern.pattern == r"^deepgram_\d{4}\.json$"
        # Test that regex works
        import re
        assert source.pattern.match("deepgram_1234.json")
        assert not source.pattern.match("deepgram_abc.json")

    def test_factory_returns_new_instance_each_time(self):
        """Test that factory returns new instances, not singletons"""
        # Execute
        source1 = InputSourceFactory.create_input_source(
            "TextFileInputSource",
            pattern=r".*\.txt$"
        )
        source2 = InputSourceFactory.create_input_source(
            "TextFileInputSource",
            pattern=r".*\.txt$"
        )

        # Assert
        assert source1 is not source2  # Different instances
        assert isinstance(source1, TextFileInputSource)
        assert isinstance(source2, TextFileInputSource)

    def test_factory_with_different_options_creates_different_instances(self):
        """Test that different options create independent instances"""
        # Execute
        source1 = InputSourceFactory.create_input_source(
            "DeepgramInputSource",
            pattern=r".*\.json$",
            format="paragraphs"
        )
        source2 = InputSourceFactory.create_input_source(
            "DeepgramInputSource",
            pattern=r".*\.json$",
            format="utterances"
        )

        # Assert
        assert source1.options["format"] == "paragraphs"
        assert source2.options["format"] == "utterances"
        assert source1 is not source2

    def test_create_all_available_sources(self):
        """Test that factory can create all known input source types"""
        # List of all input source classes that should be available
        source_classes = [
            "InputSource",  # Abstract base class - will fail instantiation
            "TextFileInputSource",
            "DeepgramInputSource",
            "InputSourceFactory"  # Factory itself
        ]

        # Test TextFileInputSource
        text_source = InputSourceFactory.create_input_source("TextFileInputSource")
        assert isinstance(text_source, TextFileInputSource)

        # Test DeepgramInputSource
        deepgram_source = InputSourceFactory.create_input_source("DeepgramInputSource")
        assert isinstance(deepgram_source, DeepgramInputSource)

    def test_factory_method_is_static(self):
        """Test that create_input_source is a static method"""
        # Should be able to call without instantiating factory
        source = InputSourceFactory.create_input_source(
            "TextFileInputSource",
            pattern=r".*\.txt$"
        )
        assert isinstance(source, TextFileInputSource)

    def test_create_with_complex_options_dict(self):
        """Test creating input source with complex nested options"""
        # Execute
        source = InputSourceFactory.create_input_source(
            "DeepgramInputSource",
            pattern=r".*\.json$",
            format="paragraphs",
            include_timestamps=True,
            speaker_labels=False,
            custom_config={
                "nested": "value",
                "number": 42
            }
        )

        # Assert
        assert source.options["custom_config"]["nested"] == "value"
        assert source.options["custom_config"]["number"] == 42

    @patch.object(sys.modules['plexus.input_sources.InputSourceFactory'], 'logging')
    def test_create_logs_error_on_failure(self, mock_logging):
        """Test that factory logs errors when creation fails"""
        # Execute
        try:
            InputSourceFactory.create_input_source("NonExistentSource")
        except ValueError:
            pass  # Expected

        # Assert
        mock_logging.error.assert_called()
        call_args = str(mock_logging.error.call_args)
        assert "Error creating input source" in call_args
        assert "NonExistentSource" in call_args

    def test_factory_consistent_with_processor_factory_pattern(self):
        """Test that InputSourceFactory follows same pattern as ProcessorFactory"""
        # This is a design consistency test
        # Both should:
        # 1. Have a static create method
        # 2. Take class name as string
        # 3. Pass **options to constructor
        # 4. Use dynamic imports
        # 5. Raise ValueError for unknown classes

        source = InputSourceFactory.create_input_source(
            "TextFileInputSource",
            pattern=r".*\.txt$",
            custom_option="value"
        )

        assert isinstance(source, TextFileInputSource)
        assert source.pattern is not None
        assert source.options["custom_option"] == "value"
