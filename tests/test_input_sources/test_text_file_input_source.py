import pytest
from unittest.mock import Mock, patch, MagicMock
from plexus.input_sources.TextFileInputSource import TextFileInputSource


class TestTextFileInputSource:
    """Test cases for TextFileInputSource"""

    @patch('plexus.input_sources.TextFileInputSource.download_score_result_log_file')
    def test_extract_successful(self, mock_download):
        """Test successful text extraction from a matching attachment"""
        # Setup
        mock_download.return_value = ("This is the file content", None)
        source = TextFileInputSource(pattern=r".*transcript\.txt$")

        item = Mock()
        item.attachedFiles = [
            "s3://bucket/path/transcript.txt",
            "s3://bucket/path/other.json"
        ]

        # Execute
        result = source.extract(item, "default_text")

        # Assert
        assert result == "This is the file content"
        mock_download.assert_called_once_with("s3://bucket/path/transcript.txt")

    @patch('plexus.input_sources.TextFileInputSource.download_score_result_log_file')
    def test_extract_multiple_matches_uses_first(self, mock_download):
        """Test that first matching attachment is used when multiple match"""
        # Setup
        mock_download.return_value = ("First file content", None)
        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.attachedFiles = [
            "s3://bucket/path/file1.txt",
            "s3://bucket/path/file2.txt",
            "s3://bucket/path/file3.json"
        ]

        # Execute
        result = source.extract(item, "default_text")

        # Assert
        assert result == "First file content"
        mock_download.assert_called_once_with("s3://bucket/path/file1.txt")

    def test_extract_no_matching_attachment(self):
        """Test that ValueError is raised when no attachment matches pattern"""
        # Setup
        source = TextFileInputSource(pattern=r".*transcript\.txt$")

        item = Mock()
        item.attachedFiles = [
            "s3://bucket/path/file1.json",
            "s3://bucket/path/file2.xml"
        ]

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            source.extract(item, "default_text")

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
            source.extract(item, "default_text")

        assert "No attachment matching pattern" in str(exc_info.value)

    def test_extract_item_is_none(self):
        """Test that ValueError is raised when item is None"""
        # Setup
        source = TextFileInputSource(pattern=r".*\.txt$")

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            source.extract(item=None, default_text="default_text")

        assert "No attachment matching pattern" in str(exc_info.value)

    def test_extract_empty_attached_files(self):
        """Test that ValueError is raised when attachedFiles is empty"""
        # Setup
        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.attachedFiles = []

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            source.extract(item, "default_text")

        assert "No attachment matching pattern" in str(exc_info.value)

    @patch('plexus.input_sources.TextFileInputSource.download_score_result_log_file')
    def test_extract_download_raises_exception(self, mock_download):
        """Test that exceptions from download propagate up"""
        # Setup
        mock_download.side_effect = Exception("S3 download failed")
        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.attachedFiles = ["s3://bucket/path/transcript.txt"]

        # Execute & Assert
        with pytest.raises(Exception, match="S3 download failed"):
            source.extract(item, "default_text")

    @patch('plexus.input_sources.TextFileInputSource.download_score_result_log_file')
    def test_extract_large_file(self, mock_download):
        """Test extraction of a large text file"""
        # Setup
        large_content = "A" * 1_000_000  # 1MB of text
        mock_download.return_value = (large_content, None)
        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.attachedFiles = ["s3://bucket/path/large.txt"]

        # Execute
        result = source.extract(item, "default_text")

        # Assert
        assert result == large_content
        assert len(result) == 1_000_000

    @patch('plexus.input_sources.TextFileInputSource.download_score_result_log_file')
    def test_extract_empty_file(self, mock_download):
        """Test extraction of an empty text file"""
        # Setup
        mock_download.return_value = ("", None)
        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.attachedFiles = ["s3://bucket/path/empty.txt"]

        # Execute
        result = source.extract(item, "default_text")

        # Assert
        assert result == ""

    @patch('plexus.input_sources.TextFileInputSource.download_score_result_log_file')
    def test_extract_file_with_unicode(self, mock_download):
        """Test extraction of file with unicode characters"""
        # Setup
        unicode_content = "Hello 世界 🌍 Привет"
        mock_download.return_value = (unicode_content, None)
        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.attachedFiles = ["s3://bucket/path/unicode.txt"]

        # Execute
        result = source.extract(item, "default_text")

        # Assert
        assert result == unicode_content

    @patch('plexus.input_sources.TextFileInputSource.download_score_result_log_file')
    def test_extract_with_options_ignored(self, mock_download):
        """Test that extra options don't affect TextFileInputSource behavior"""
        # Setup
        mock_download.return_value = ("File content", None)
        source = TextFileInputSource(
            pattern=r".*\.txt$",
            extra_option="ignored",
            another_option=123
        )

        item = Mock()
        item.attachedFiles = ["s3://bucket/path/file.txt"]

        # Execute
        result = source.extract(item, "default_text")

        # Assert
        assert result == "File content"
        assert source.options == {"extra_option": "ignored", "another_option": 123}

    @patch('plexus.input_sources.TextFileInputSource.download_score_result_log_file')
    def test_extract_complex_s3_path(self, mock_download):
        """Test extraction with complex S3 path structure"""
        # Setup
        mock_download.return_value = ("Content", None)
        source = TextFileInputSource(pattern=r".*deepgram.*\.txt$")

        item = Mock()
        item.attachedFiles = [
            "s3://my-bucket/tenant-123/items/456/attachments/deepgram_transcript.txt"
        ]

        # Execute
        result = source.extract(item, "default_text")

        # Assert
        assert result == "Content"
        mock_download.assert_called_once_with(
            "s3://my-bucket/tenant-123/items/456/attachments/deepgram_transcript.txt"
        )

    def test_default_text_parameter_not_used(self):
        """Test that default_text parameter is not used in TextFileInputSource"""
        # This is by design - TextFileInputSource raises error if no match found,
        # rather than falling back to default_text
        source = TextFileInputSource(pattern=r".*\.txt$")

        item = Mock()
        item.attachedFiles = ["s3://bucket/path/file.json"]

        with pytest.raises(ValueError):
            source.extract(item, "this_default_should_not_be_used")
