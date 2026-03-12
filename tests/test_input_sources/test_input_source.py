import pytest
import re
from unittest.mock import Mock, MagicMock
from plexus.input_sources.InputSource import InputSource


class ConcreteInputSource(InputSource):
    """Concrete implementation for testing abstract base class"""
    def extract(self, item, default_text: str) -> str:
        return "extracted_text"


class TestInputSource:
    """Test cases for InputSource base class"""

    def test_init_with_pattern(self):
        """Test initialization with a regex pattern"""
        source = ConcreteInputSource(pattern=r".*\.txt$")
        assert source.pattern is not None
        assert isinstance(source.pattern, re.Pattern)
        assert source.options == {}

    def test_init_with_pattern_and_options(self):
        """Test initialization with pattern and additional options"""
        source = ConcreteInputSource(
            pattern=r".*\.json$",
            format="paragraphs",
            include_timestamps=True
        )
        assert source.pattern is not None
        assert source.options == {
            "format": "paragraphs",
            "include_timestamps": True
        }

    def test_init_without_pattern(self):
        """Test initialization without a pattern"""
        source = ConcreteInputSource()
        assert source.pattern is None
        assert source.options == {}

    def test_find_matching_attachment_no_pattern(self):
        """Test that find_matching_attachment raises error when no pattern set"""
        source = ConcreteInputSource()
        item = Mock()
        item.attachedFiles = ["file1.txt", "file2.json"]

        with pytest.raises(ValueError, match="requires a pattern"):
            source.find_matching_attachment(item)

    def test_find_matching_attachment_no_item(self):
        """Test finding attachment when item is None"""
        source = ConcreteInputSource(pattern=r".*\.txt$")
        result = source.find_matching_attachment(None)
        assert result is None

    def test_find_matching_attachment_no_attached_files(self):
        """Test finding attachment when item has no attachedFiles attribute"""
        source = ConcreteInputSource(pattern=r".*\.txt$")
        item = Mock(spec=[])  # Item with no attributes
        result = source.find_matching_attachment(item)
        assert result is None

    def test_find_matching_attachment_empty_list(self):
        """Test finding attachment when attachedFiles is empty"""
        source = ConcreteInputSource(pattern=r".*\.txt$")
        item = Mock()
        item.attachedFiles = []
        result = source.find_matching_attachment(item)
        assert result is None

    def test_find_matching_attachment_single_match(self):
        """Test finding a single matching attachment"""
        source = ConcreteInputSource(pattern=r".*\.txt$")
        item = Mock()
        item.attachedFiles = [
            "s3://bucket/path/file1.json",
            "s3://bucket/path/transcript.txt",
            "s3://bucket/path/file2.json"
        ]
        result = source.find_matching_attachment(item)
        assert result == "s3://bucket/path/transcript.txt"

    def test_find_matching_attachment_multiple_matches(self):
        """Test that first matching attachment is returned"""
        source = ConcreteInputSource(pattern=r".*\.txt$")
        item = Mock()
        item.attachedFiles = [
            "s3://bucket/path/file1.txt",
            "s3://bucket/path/file2.txt",
            "s3://bucket/path/file3.json"
        ]
        result = source.find_matching_attachment(item)
        assert result == "s3://bucket/path/file1.txt"

    def test_find_matching_attachment_no_match(self):
        """Test finding attachment when no files match pattern"""
        source = ConcreteInputSource(pattern=r".*\.txt$")
        item = Mock()
        item.attachedFiles = [
            "s3://bucket/path/file1.json",
            "s3://bucket/path/file2.pdf",
            "s3://bucket/path/file3.xml"
        ]
        result = source.find_matching_attachment(item)
        assert result is None

    def test_find_matching_attachment_complex_pattern(self):
        """Test finding attachment with complex regex pattern"""
        source = ConcreteInputSource(pattern=r".*deepgram.*\.json$")
        item = Mock()
        item.attachedFiles = [
            "s3://bucket/path/transcript.txt",
            "s3://bucket/path/deepgram_result.json",
            "s3://bucket/path/deepgram_metadata.xml"
        ]
        result = source.find_matching_attachment(item)
        assert result == "s3://bucket/path/deepgram_result.json"

    def test_find_matching_attachment_extracts_filename_from_path(self):
        """Test that pattern matching works on filename only, not full path"""
        source = ConcreteInputSource(pattern=r"^deepgram.*\.json$")
        item = Mock()
        item.attachedFiles = [
            "s3://bucket/path/with/deepgram/in/path/other.txt",
            "s3://bucket/another/path/deepgram_result.json"
        ]
        result = source.find_matching_attachment(item)
        # Should match the filename "deepgram_result.json", not the path with "deepgram" in it
        assert result == "s3://bucket/another/path/deepgram_result.json"

    def test_extract_is_abstract(self):
        """Test that extract method must be implemented by subclasses"""
        # Attempting to instantiate InputSource directly should fail
        with pytest.raises(TypeError):
            InputSource(pattern=r".*\.txt$")

    def test_concrete_extract_implementation(self):
        """Test that concrete implementation's extract method works"""
        source = ConcreteInputSource(pattern=r".*\.txt$")
        item = Mock()
        result = source.extract(item, "default_text")
        assert result == "extracted_text"

    def test_logger_is_created(self):
        """Test that logger is created with correct name"""
        source = ConcreteInputSource()
        assert source.logger is not None
        assert source.logger.name == "ConcreteInputSource"
