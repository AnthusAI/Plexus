import pytest
import sys
from unittest.mock import Mock, patch

# Import to ensure module is loaded
from plexus.input_sources.TextFileInputSource import TextFileInputSource


class TestTextFileInputSource:
    """Test cases for TextFileInputSource"""

    @patch.object(sys.modules['plexus.input_sources.TextFileInputSource'], 'download_score_result_log_file')
    def test_extract_successful(self, mock_download):
        """Test successful text extraction from a matching attachment"""
        mock_download.return_value = ("This is the file content", None)

        source = TextFileInputSource(pattern=r".*transcript\.txt$")

        item = Mock()
        item.metadata = {}
        item.attachedFiles = [
            "s3://bucket/path/transcript.txt",
            "s3://bucket/path/other.json"
        ]

        # Execute
        result = source.extract(item)

        # Assert
        assert result.text == "This is the file content"
        mock_download.assert_called_once()

    @patch.object(sys.modules['plexus.input_sources.TextFileInputSource'], 'download_score_result_log_file')
    def test_extract_multiple_matches_uses_first(self, mock_download):
        """Test that first matching attachment is used when multiple match"""
        mock_download.return_value = ("First file content", None)

        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.metadata = {}
        item.attachedFiles = [
            "s3://bucket/path/file1.txt",
            "s3://bucket/path/file2.txt",
            "s3://bucket/path/file3.json"
        ]

        # Execute
        result = source.extract(item)

        # Assert
        assert result.text == "First file content"
        mock_download.assert_called_once()

    def test_extract_no_matching_attachment(self):
        """Test that ValueError is raised when no attachment matches pattern"""
        # Setup
        source = TextFileInputSource(pattern=r".*transcript\.txt$")

        item = Mock()
        item.metadata = {}
        item.attachedFiles = [
            "s3://bucket/path/file1.json",
            "s3://bucket/path/file2.xml"
        ]

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            source.extract(item)

        assert "No attachment matching pattern" in str(exc_info.value)
        assert ".*transcript\\.txt$" in str(exc_info.value)
        assert "Available attachments:" in str(exc_info.value)

    def test_extract_item_has_no_attached_files(self):
        """Test that ValueError is raised when item has no attachedFiles"""
        # Setup
        source = TextFileInputSource(pattern=r".*\.txt$")
        item = Mock(spec=[])  # Item with no attributes

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            source.extract(item)

        assert "No attachment matching pattern" in str(exc_info.value)

    def test_extract_item_is_none(self):
        """Test that ValueError is raised when item is None"""
        # Setup
        source = TextFileInputSource(pattern=r".*\.txt$")

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            source.extract(item=None)

        assert "No attachment matching pattern" in str(exc_info.value)

    def test_extract_empty_attached_files(self):
        """Test that ValueError is raised when attachedFiles is empty"""
        # Setup
        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.metadata = {}
        item.attachedFiles = []

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            source.extract(item)

        assert "No attachment matching pattern" in str(exc_info.value)

    @patch.object(sys.modules['plexus.input_sources.TextFileInputSource'], 'download_score_result_log_file')
    def test_extract_download_raises_exception(self, mock_download):
        """Test that exceptions from download propagate up"""
        mock_download.side_effect = Exception("S3 download failed")

        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/path/transcript.txt"]

        # Execute & Assert
        with pytest.raises(Exception, match="S3 download failed"):
            source.extract(item)

    @patch.object(sys.modules['plexus.input_sources.TextFileInputSource'], 'download_score_result_log_file')
    def test_extract_large_file(self, mock_download):
        """Test extraction of a large text file"""
        large_content = "A" * 1_000_000  # 1MB of text
        mock_download.return_value = (large_content, None)

        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/path/large.txt"]

        # Execute
        result = source.extract(item)

        # Assert
        assert result.text == large_content
        assert len(result.text) == 1_000_000

    @patch.object(sys.modules['plexus.input_sources.TextFileInputSource'], 'download_score_result_log_file')
    def test_extract_empty_file(self, mock_download):
        """Test extraction of an empty text file"""
        mock_download.return_value = ("", None)

        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/path/empty.txt"]

        # Execute
        result = source.extract(item)

        # Assert
        assert result.text == ""

    @patch.object(sys.modules['plexus.input_sources.TextFileInputSource'], 'download_score_result_log_file')
    def test_extract_file_with_unicode(self, mock_download):
        """Test extraction of file with unicode characters"""
        mock_download.return_value = ("Hello 世界 🌍 Привет", None)

        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/path/unicode.txt"]

        # Execute
        result = source.extract(item)

        # Assert
        assert result.text == "Hello 世界 🌍 Привет"

    @patch.object(sys.modules['plexus.input_sources.TextFileInputSource'], 'download_score_result_log_file')
    def test_extract_with_options_ignored(self, mock_download):
        """Test that extra options don't affect TextFileInputSource behavior"""
        mock_download.return_value = ("File content", None)

        source = TextFileInputSource(
            pattern=r".*\.txt$",
            extra_option="ignored",
            another_option=123
        )

        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/path/file.txt"]

        # Execute
        result = source.extract(item)

        # Assert
        assert result.text == "File content"
        assert source.options == {"extra_option": "ignored", "another_option": 123}

    @patch.object(sys.modules['plexus.input_sources.TextFileInputSource'], 'download_score_result_log_file')
    def test_extract_complex_s3_path(self, mock_download):
        """Test extraction with complex S3 path structure"""
        mock_download.return_value = ("Content", None)

        source = TextFileInputSource(pattern=r".*deepgram.*\.txt$")

        item = Mock()
        item.metadata = {}
        item.attachedFiles = [
            "s3://my-bucket/tenant-123/items/456/attachments/deepgram_transcript.txt"
        ]

        # Execute
        result = source.extract(item)

        # Assert
        assert result.text == "Content"
        mock_download.assert_called_once()

    def test_default_text_parameter_not_used(self):
        """Test that default_text parameter is not used in TextFileInputSource"""
        # This is by design - TextFileInputSource raises error if no match found,
        # rather than falling back to default_text
        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/path/file.json"]

        with pytest.raises(ValueError):
            source.extract(item)
